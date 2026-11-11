from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import services


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


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
        tutor = make_user("tutor@example.com")
        self.assertIsNone(services.get_earliest_activity(tutor.id))

    def test_returns_earliest_across_entities(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        earliest = services.get_earliest_activity(tutor.id)
        self.assertIsNotNone(earliest)

    def test_ignores_other_accounts(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        Student.objects.create(user=other, first_name="Pat", last_name="Jones")
        self.assertIsNone(services.get_earliest_activity(tutor.id))


class GetTrendsTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.tutor, first_name="Jo", last_name="Payer")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", payee=self.payee, hourly_rate=40)

    def test_new_student_counted_in_window_and_roster_carries_baseline_forward(self):
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=60)
        filters = services.Filters(start=start, end=now, user_id=self.tutor.id, granularity="month")
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

        filters = services.Filters(start=start, end=now, user_id=self.tutor.id, granularity="month")
        trends = services.get_trends(filters, now=now)

        sessions_chart = next(c for c in trends["charts"] if c["key"] == "sessions")
        sessions_count = next(s for s in sessions_chart["series"] if s["key"] == "sessions_count")
        sessions_hours = next(s for s in sessions_chart["series"] if s["key"] == "sessions_hours")
        self.assertEqual(sessions_count["total"], 1)
        self.assertEqual(sessions_hours["total"], 1.0)

        payments_chart = next(c for c in trends["charts"] if c["key"] == "payments")
        payments_amount = next(s for s in payments_chart["series"] if s["key"] == "payments_amount")
        self.assertEqual(payments_amount["total"], 100.0)

    def test_never_counts_another_accounts_data(self):
        other = make_user("other@example.com")
        other_payee = Payee.objects.create(user=other, first_name="Lee", last_name="Other")
        other_student = Student.objects.create(user=other, first_name="Pat", last_name="Jones", payee=other_payee)
        now = datetime.now(timezone.utc)
        Session.objects.create(
            user=other,
            student=other_student,
            session_date=now - timedelta(days=1),
            session_start_time=now - timedelta(days=1),
            session_end_time=now - timedelta(days=1) + timedelta(hours=1),
        )
        Payment.objects.create(user=other, payee=other_payee, amount=Decimal("50.00"), payment_date=now - timedelta(days=1))

        # Even when filtering by the other account's student/payee ids.
        for extra in ({}, {"student_id": other_student.id}, {"payee_id": other_payee.id}):
            filters = services.Filters(start=now - timedelta(days=90), end=now, user_id=self.tutor.id, granularity="month", **extra)
            trends = services.get_trends(filters, now=now)
            totals = {s["key"]: s["total"] for c in trends["charts"] for s in c["series"]}
            self.assertEqual(totals["sessions_count"], 0, extra)
            self.assertEqual(totals["payments_amount"], 0, extra)
            expected_roster = 0.0 if extra else 1.0  # only self.student, and only unfiltered
            self.assertEqual(totals["students_roster"], expected_roster, extra)


class FilterOptionsTests(APITestCase):
    def test_returns_own_students_and_payees_only(self):
        tutor = make_user("tutor@example.com")
        payee = Payee.objects.create(user=tutor, first_name="Jo", last_name="Payer")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", payee=payee)
        other = make_user("other@example.com")
        Payee.objects.create(user=other, first_name="Lee", last_name="Other")
        Student.objects.create(user=other, first_name="Pat", last_name="Jones")

        options = services.get_filter_options(tutor.id)
        self.assertEqual([o["name"] for o in options["students"]], ["Sam Smith"])
        self.assertEqual([o["name"] for o in options["payees"]], ["Jo Payer"])
        self.assertNotIn("tutors", options)


class ViewPermissionTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")

    def test_any_account_can_view_trends(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(reverse("analytics-trends"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("charts", response.data)

    def test_filters_only_list_own_students(self):
        Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones")
        self.client.force_authenticate(self.tutor)
        response = self.client.get(reverse("analytics-filters"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([o["name"] for o in response.data["students"]], ["Sam Smith"])

    def test_unauthenticated_cannot_view_trends(self):
        response = self.client.get(reverse("analytics-trends"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
