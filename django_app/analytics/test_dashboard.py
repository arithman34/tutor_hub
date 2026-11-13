"""The dashboard's numbers: like-for-like month comparisons, the revenue chart,
upcoming sessions and the per-student breakdown."""

from datetime import date, datetime, timedelta, timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import dashboard
from .serializers import RevenueByMonthSerializer, StudentBreakdownSerializer, UpcomingSessionsSerializer

# 13 Nov 2026, 10:00 UTC (also 10:00 in London: GMT).
NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


def at(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class DashboardDataTestCase(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.payee = Payee.objects.create(user=self.user, first_name="Pat", last_name="Payer")
        self.student = Student.objects.create(
            user=self.user, payee=self.payee, first_name="Sam", last_name="Smith", level="GCSE", hourly_rate=40
        )

    def pay(self, amount, when, user=None, payee=None):
        Payment.objects.create(user=user or self.user, payee=payee or self.payee, amount=amount, payment_date=when)

    def lesson(self, start, minutes=60, student=None, **extra):
        student = student or self.student
        Session.objects.create(
            user=student.user,
            student=student,
            session_date=start,
            session_start_time=start,
            session_end_time=start + timedelta(minutes=minutes),
            **extra,
        )


class SamePeriodTests(APITestCase):
    def test_same_days_of_last_month(self):
        self.assertEqual(dashboard.same_period_last_month(NOW), (at(2026, 10, 1, 0), at(2026, 10, 14, 0)))

    def test_clamped_to_a_shorter_last_month(self):
        start, end = dashboard.same_period_last_month(at(2026, 3, 31))
        self.assertEqual((start, end), (at(2026, 2, 1, 0), at(2026, 3, 1, 0)))

    def test_january_compares_with_december(self):
        self.assertEqual(dashboard.same_period_last_month(at(2027, 1, 5)), (at(2026, 12, 1, 0), at(2026, 12, 6, 0)))


class DashboardStatsTests(DashboardDataTestCase):
    def test_revenue_change_is_against_the_same_days_last_month(self):
        self.pay(100, at(2026, 11, 2))
        self.pay(80, at(2026, 10, 5))
        self.pay(500, at(2026, 10, 28))  # After 13 Oct, so not in the comparison.

        stats = dashboard.get_dashboard_stats(self.user, now=NOW)

        self.assertEqual(stats["revenue_this_month"], 100)
        self.assertEqual(stats["revenue_same_period_last_month"], 80)
        self.assertEqual(stats["mom_trend"], 25.0)
        self.assertEqual((stats["compare_from"], stats["compare_to"]), (date(2026, 10, 1), date(2026, 10, 13)))

    def test_projection_adds_the_rest_of_last_month(self):
        self.pay(100, at(2026, 11, 2))
        self.pay(80, at(2026, 10, 5))
        self.pay(500, at(2026, 10, 28))

        self.assertEqual(dashboard.get_dashboard_stats(self.user, now=NOW)["revenue_projected"], 600)

    def test_no_projection_without_last_month(self):
        self.pay(100, at(2026, 11, 2))
        stats = dashboard.get_dashboard_stats(self.user, now=NOW)
        self.assertIsNone(stats["revenue_projected"])
        self.assertIsNone(stats["mom_trend"])

    def test_month_to_date_running_total_has_one_value_per_day(self):
        self.pay(30, at(2026, 11, 2))
        self.pay(20, at(2026, 11, 10))

        series = dashboard.get_dashboard_stats(self.user, now=NOW)["revenue_month_to_date"]

        self.assertEqual(len(series), 13)
        self.assertEqual(series[0], 0)
        self.assertEqual(series[1], 30)
        self.assertEqual(series[-1], 50)

    def test_sessions_and_hours_compare_like_for_like(self):
        self.lesson(at(2026, 11, 3), minutes=90)
        self.lesson(at(2026, 11, 10))
        self.lesson(at(2026, 10, 6))
        self.lesson(at(2026, 10, 20))  # Outside 1-13 Oct.
        self.lesson(at(2026, 11, 20))  # Booked, not taught yet.

        stats = dashboard.get_dashboard_stats(self.user, now=NOW)

        self.assertEqual(stats["sessions_this_month"], 2)
        self.assertEqual(stats["sessions_pct_change"], 100.0)
        self.assertEqual(stats["hours_this_month"], 2.5)
        self.assertEqual(stats["hours_pct_change"], 150.0)
        self.assertEqual(stats["students_taught_this_month"], 1)

    def test_sessions_this_week_compared_with_the_week_before(self):
        self.lesson(at(2026, 11, 10))
        self.lesson(at(2026, 11, 12))
        self.lesson(at(2026, 11, 4))

        stats = dashboard.get_dashboard_stats(self.user, now=NOW)

        self.assertEqual(stats["sessions_this_week"], 2)
        self.assertEqual(stats["sessions_week_pct_change"], 100.0)

    def test_average_hourly_rate_is_revenue_over_hours_this_year(self):
        self.pay(90, at(2026, 3, 1))
        self.lesson(at(2026, 2, 1), minutes=120)
        self.lesson(at(2025, 12, 1), minutes=600)  # Last year: not counted.

        stats = dashboard.get_dashboard_stats(self.user, now=NOW)

        self.assertEqual(stats["hours_this_year"], 2)
        self.assertEqual(stats["average_hourly_rate"], 45)

    def test_no_average_rate_without_hours(self):
        self.assertIsNone(dashboard.get_dashboard_stats(self.user, now=NOW)["average_hourly_rate"])


class RevenueByMonthTests(DashboardDataTestCase):
    def test_twelve_months_oldest_first_with_the_current_one_in_progress(self):
        self.pay(100, at(2026, 11, 2))
        self.pay(40, at(2025, 12, 20))
        self.pay(999, at(2025, 11, 30))  # Thirteen months back: left out.

        months = dashboard.get_revenue_by_month(self.user, now=NOW)

        self.assertEqual(len(months), 12)
        self.assertEqual(months[0], {"month": date(2025, 12, 1), "revenue": 40, "in_progress": False})
        self.assertEqual(months[-1], {"month": date(2026, 11, 1), "revenue": 100, "in_progress": True})
        self.assertEqual(sum(month["in_progress"] for month in months), 1)

    def test_ignores_other_accounts(self):
        other = make_user("other@example.com")
        other_payee = Payee.objects.create(user=other, first_name="O", last_name="P")
        self.pay(100, at(2026, 11, 2), user=other, payee=other_payee)

        self.assertEqual(sum(month["revenue"] for month in dashboard.get_revenue_by_month(self.user, now=NOW)), 0)


class UpcomingSessionsTests(DashboardDataTestCase):
    def test_today_and_the_next_few_days_soonest_first(self):
        self.lesson(at(2026, 11, 16, 17), topic_tags="algebra")  # Day 4.
        self.lesson(at(2026, 11, 13, 16))  # Later today.
        self.lesson(at(2026, 11, 13, 8))  # Earlier today, finished.
        self.lesson(at(2026, 11, 17, 9))  # Day 5: too far ahead.

        sessions = dashboard.get_upcoming_sessions(self.user, now=NOW)

        self.assertEqual([s["start"] for s in sessions], [at(2026, 11, 13, 16), at(2026, 11, 16, 17)])
        self.assertEqual(sessions[0]["student_name"], "Sam Smith")
        self.assertEqual(sessions[0]["level"], "GCSE")
        self.assertIsNone(sessions[0]["topic_tags"])
        self.assertEqual(sessions[1]["topic_tags"], "algebra")

    def test_includes_a_lesson_in_progress(self):
        self.lesson(at(2026, 11, 13, 9), minutes=90)  # 09:00-10:30, and it's 10:00.
        self.assertEqual(len(dashboard.get_upcoming_sessions(self.user, now=NOW)), 1)

    def test_uses_wall_clock_time_in_summer(self):
        # 15:30 UTC is 16:30 in London in July, so the 16:00 lesson has started, not finished.
        summer_now = datetime(2026, 7, 6, 15, 30, tzinfo=timezone.utc)
        self.lesson(at(2026, 7, 6, 16))
        self.assertEqual(len(dashboard.get_upcoming_sessions(self.user, now=summer_now)), 1)
        self.assertEqual(len(dashboard.get_upcoming_sessions(self.user, now=summer_now + timedelta(hours=1))), 0)


class StudentBreakdownTests(DashboardDataTestCase):
    def test_hours_and_billed_revenue_per_student_most_revenue_first(self):
        other_student = Student.objects.create(user=self.user, first_name="Alex", last_name="Jones", hourly_rate=30)
        unpriced = Student.objects.create(user=self.user, first_name="Chris", last_name="Lee")
        self.lesson(at(2026, 11, 3), minutes=90)
        self.lesson(at(2026, 11, 10))
        self.lesson(at(2026, 11, 4), student=other_student, minutes=120)
        self.lesson(at(2026, 11, 5), student=unpriced)
        self.lesson(at(2026, 10, 30))  # Last month.
        self.lesson(at(2026, 11, 20))  # Not taught yet.

        rows = dashboard.get_student_breakdown(self.user, now=NOW)

        self.assertEqual([row["student_name"] for row in rows], ["Sam Smith", "Alex Jones", "Chris Lee"])
        self.assertEqual((rows[0]["sessions"], rows[0]["hours"], rows[0]["revenue"]), (2, 2.5, 100))
        self.assertEqual((rows[1]["hours"], rows[1]["revenue"]), (2, 60))
        self.assertEqual((rows[2]["revenue"], rows[2]["hourly_rate"]), (0, None))


class DashboardEndpointTests(DashboardDataTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def assert_matches(self, serializer_class, data):
        serializer = serializer_class(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_revenue(self):
        response = self.client.get("/api/v1/analytics/dashboard/revenue")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_matches(RevenueByMonthSerializer, response.json())
        self.assertEqual(len(response.json()["months"]), 12)

    def test_upcoming(self):
        self.lesson(datetime.now(timezone.utc) + timedelta(days=1))
        response = self.client.get("/api/v1/analytics/dashboard/upcoming", {"days": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_matches(UpcomingSessionsSerializer, response.json())
        self.assertEqual(len(response.json()["sessions"]), 1)

    def test_upcoming_rejects_too_many_days(self):
        response = self.client.get("/api/v1/analytics/dashboard/upcoming", {"days": 60})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_students(self):
        response = self.client.get("/api/v1/analytics/dashboard/students")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_matches(StudentBreakdownSerializer, response.json())

    def test_only_own_sessions(self):
        other = make_user("other@example.com")
        their_student = Student.objects.create(user=other, first_name="Not", last_name="Mine", hourly_rate=50)
        self.lesson(datetime.now(timezone.utc) + timedelta(hours=26), student=their_student)

        self.assertEqual(self.client.get("/api/v1/analytics/dashboard/upcoming").json()["sessions"], [])

    def test_all_require_authentication(self):
        for path in ("revenue", "upcoming", "students"):
            with self.subTest(path=path):
                response = APIClient().get(f"/api/v1/analytics/dashboard/{path}")
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
