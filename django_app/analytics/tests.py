from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import services


def make_user(email, role=UserRole.TUTOR):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role)


class BucketMathTests(APITestCase):
    def test_floor_bucket_day(self):
        moment = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(services.floor_bucket(moment, "day"), datetime(2026, 6, 15, tzinfo=timezone.utc))

    def test_floor_bucket_week_snaps_to_monday(self):
        # 2026-06-18 is a Thursday
        moment = datetime(2026, 6, 18, tzinfo=timezone.utc)
        self.assertEqual(services.floor_bucket(moment, "week"), datetime(2026, 6, 15, tzinfo=timezone.utc))

    def test_floor_bucket_month(self):
        moment = datetime(2026, 6, 18, tzinfo=timezone.utc)
        self.assertEqual(services.floor_bucket(moment, "month"), datetime(2026, 6, 1, tzinfo=timezone.utc))

    def test_step_bucket_month_rolls_year(self):
        december = datetime(2026, 12, 1, tzinfo=timezone.utc)
        self.assertEqual(services.step_bucket(december, "month"), datetime(2027, 1, 1, tzinfo=timezone.utc))

    def test_step_bucket_month_backward_rolls_year(self):
        january = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(services.step_bucket(january, "month", forward=False), datetime(2026, 12, 1, tzinfo=timezone.utc))

    def test_bucket_range_month_inclusive(self):
        start = datetime(2026, 1, 15, tzinfo=timezone.utc)
        end = datetime(2026, 3, 1, tzinfo=timezone.utc)
        buckets = services.bucket_range(start, end, "month")
        self.assertEqual(buckets, [datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc)])

    def test_fit_granularity_coarsens_when_too_many_buckets(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # ~6 years of days is over MAX_BUCKETS, so it coarsens one step to week
        # (~313 weeks, still under 400) rather than all the way to month.
        self.assertEqual(services.fit_granularity(start, end, "day"), "week")

    def test_fit_granularity_coarsens_to_month_for_very_long_range(self):
        start = datetime(2000, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(services.fit_granularity(start, end, "day"), "month")

    def test_fit_granularity_keeps_fine_granularity_for_small_range(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.assertEqual(services.fit_granularity(start, end, "day"), "day")

    def test_pct_change_with_no_baseline_is_none(self):
        self.assertIsNone(services.pct_change(10, 0))

    def test_pct_change_computes_percentage(self):
        self.assertEqual(services.pct_change(150, 100), 50.0)


class ResolveRangeTests(APITestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

    def test_preset_12m_default(self):
        preset, start, end = services.resolve_range(None, None, None, None, self.now)
        self.assertEqual(preset, "12m")
        self.assertEqual(start, datetime(2025, 7, 1, tzinfo=timezone.utc))

    def test_preset_3m(self):
        preset, start, end = services.resolve_range("3m", None, None, None, self.now)
        self.assertEqual(preset, "3m")
        self.assertEqual(start, datetime(2026, 4, 1, tzinfo=timezone.utc))

    def test_preset_ytd(self):
        preset, start, end = services.resolve_range("ytd", None, None, None, self.now)
        self.assertEqual(start, datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_custom_dates_win_over_preset(self):
        preset, start, end = services.resolve_range("3m", date(2026, 1, 1), date(2026, 2, 1), None, self.now)
        self.assertEqual(preset, "custom")
        self.assertEqual(start.date(), date(2026, 1, 1))
        self.assertEqual(end.date(), date(2026, 2, 1))

    def test_inverted_custom_dates_are_swapped(self):
        preset, start, end = services.resolve_range(None, date(2026, 3, 1), date(2026, 1, 1), None, self.now)
        self.assertLess(start, end)

    def test_preset_all_falls_back_without_earliest(self):
        preset, start, end = services.resolve_range("all", None, None, None, self.now)
        self.assertEqual(preset, "all")
        self.assertEqual(start, datetime(2025, 7, 1, tzinfo=timezone.utc))


class EarliestActivityTests(APITestCase):
    def test_none_when_no_data(self):
        self.assertIsNone(services.get_earliest_activity())

    def test_returns_earliest_across_entities(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        earliest = services.get_earliest_activity()
        self.assertIsNotNone(earliest)


class GetTrendsTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", payee=self.payee, hourly_rate=40)

    def test_new_student_counted_in_window_and_roster_carries_baseline_forward(self):
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=60)
        filters = services.Filters(start=start, end=now, granularity="month")
        trends = services.get_trends(filters, now=now)

        students_chart = next(c for c in trends["charts"] if c["key"] == "students")
        new_series = next(s for s in students_chart["series"] if s["key"] == "students_new")
        roster_series = next(s for s in students_chart["series"] if s["key"] == "students_roster")

        # self.student was created "now" (in setUp), inside the window.
        self.assertEqual(sum(new_series["data"]), 1)
        self.assertEqual(roster_series["total"], 1.0)

    def test_session_and_payment_series_reflect_recorded_activity(self):
        now = datetime.now(timezone.utc)
        start = (now.replace(day=1) - timedelta(days=60)).replace(day=1)
        session_time = now - timedelta(days=5)
        Session.objects.create(
            user=self.tutor,
            student=self.student,
            session_date=session_time,
            session_start_time=session_time,
            session_end_time=session_time + timedelta(hours=1),
        )
        Payment.objects.create(user=self.tutor, payee=self.payee, amount=Decimal("100.00"), payment_date=now - timedelta(days=5))

        filters = services.Filters(start=start, end=now, granularity="month")
        trends = services.get_trends(filters, now=now)

        sessions_chart = next(c for c in trends["charts"] if c["key"] == "sessions")
        sessions_count = next(s for s in sessions_chart["series"] if s["key"] == "sessions_count")
        sessions_hours = next(s for s in sessions_chart["series"] if s["key"] == "sessions_hours")
        self.assertEqual(sessions_count["total"], 1)
        self.assertEqual(sessions_hours["total"], 1.0)

        payments_chart = next(c for c in trends["charts"] if c["key"] == "payments")
        payments_amount = next(s for s in payments_chart["series"] if s["key"] == "payments_amount")
        self.assertEqual(payments_amount["total"], 100.0)

    def test_filters_scope_to_tutor(self):
        other_tutor = make_user("other@example.com")
        Student.objects.create(user=other_tutor, first_name="Pat", last_name="Jones")

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=90)
        filters = services.Filters(start=start, end=now, granularity="month", tutor_id=self.tutor.id)
        trends = services.get_trends(filters, now=now)

        students_chart = next(c for c in trends["charts"] if c["key"] == "students")
        roster_series = next(s for s in students_chart["series"] if s["key"] == "students_roster")
        # Only self.student (belongs to self.tutor) should count, not other_tutor's student.
        self.assertEqual(roster_series["total"], 1.0)


class FilterOptionsTests(APITestCase):
    def test_returns_tutors_students_and_payees(self):
        tutor = make_user("tutor@example.com")
        payee = Payee.objects.create(user=tutor, first_name="Jo", last_name="Payer")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", payee=payee)

        options = services.get_filter_options()
        self.assertEqual(len(options["tutors"]), 1)
        self.assertEqual(len(options["students"]), 1)
        self.assertEqual(len(options["payees"]), 1)

    def test_admin_only_role_excluded_from_tutor_options(self):
        make_user("admin@example.com", UserRole.ADMIN)
        options = services.get_filter_options()
        self.assertEqual(options["tutors"], [])


class ViewPermissionTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")

    def test_tutor_cannot_view_trends(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(reverse("analytics-trends"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_trends(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("analytics-trends"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("charts", response.data)

    def test_admin_can_view_filters(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("analytics-filters"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tutors", response.data)

    def test_unauthenticated_cannot_view_trends(self):
        response = self.client.get(reverse("analytics-trends"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
