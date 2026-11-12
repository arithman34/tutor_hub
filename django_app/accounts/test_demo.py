"""The read-only demo account: its records, its sign-in, and what it may change."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from rest_framework.views import APIView

from analytics.dashboard import get_dashboard_stats
from assistant.models import AssistantUsage
from assistant.views import AskView, ResetView
from billing.models import Payee, Payment
from billing.services import payee_balances
from calendar_integration import services as calendar_services
from students.models import Student
from tutoring_sessions.models import Session

from . import demo
from .models import User

# The only API views the demo may call with POST and friends. Neither changes
# what the next visitor sees: the AI chat lives in each visitor's session.
DEMO_WRITABLE = {AskView, ResetView}


def make_real_user(email="tutor@gmail.com"):
    return User.objects.create_user(email=email, password="x", first_name="Ada", last_name="Lovelace")


class FillTests(TestCase):
    def test_creates_a_year_of_records_the_pages_can_show(self):
        user = demo.get_or_create_user()
        counts = demo.fill(user)

        self.assertEqual(counts["students"], 9)
        self.assertEqual(Student.objects.filter(user=user, is_active=False).count(), 2)
        sessions = Session.objects.filter(user=user)
        self.assertEqual(sessions.count(), counts["sessions"])
        self.assertGreater(sessions.count(), 200)
        self.assertTrue(sessions.filter(is_no_show=True).exists())
        self.assertTrue(sessions.exclude(work_covered=None).exists())
        # A no-show never has notes.
        self.assertFalse(sessions.filter(is_no_show=True).exclude(work_covered=None).exists())

        stats = get_dashboard_stats(user)
        self.assertGreater(stats["revenue_this_year"], 0)
        self.assertGreater(stats["outstanding_total"], 0)
        # Most families are settled up to last month; at least one owes more.
        balances = payee_balances(list(user.payees.all()))
        self.assertTrue(any(balance < 0 for balance in balances.values()))

    def test_replaces_the_previous_records(self):
        user = demo.get_or_create_user()
        demo.fill(user)
        first = (Session.objects.count(), Payment.objects.count(), Payee.objects.count())
        demo.fill(user)
        self.assertEqual((Session.objects.count(), Payment.objects.count(), Payee.objects.count()), first)

    def test_leaves_other_accounts_alone(self):
        real = make_real_user()
        Student.objects.create(user=real, first_name="Sam", last_name="Smith")
        demo.fill(demo.get_or_create_user())
        self.assertEqual(Student.objects.filter(user=real).count(), 1)

    def test_refuses_a_real_account(self):
        real = make_real_user()
        Student.objects.create(user=real, first_name="Sam", last_name="Smith")
        with self.assertRaises(ValueError):
            demo.fill(real)
        self.assertEqual(Student.objects.filter(user=real).count(), 1)


class SignInTests(TestCase):
    def test_creates_the_account_on_first_use_without_a_password(self):
        user = demo.sign_in()
        self.assertTrue(user.is_demo)
        self.assertEqual(user.email, "demo@tutorhub.test")
        self.assertFalse(user.has_usable_password())
        self.assertIsNotNone(user.demo_seeded_at)
        self.assertGreater(Session.objects.filter(user=user).count(), 200)

    @override_settings(DEMO_AI_DAILY_LIMIT=5)
    def test_caps_the_shared_ai_allowance(self):
        self.assertEqual(demo.sign_in().assistant_daily_limit, 5)

    def test_keeps_records_less_than_a_week_old(self):
        user = demo.sign_in()
        with mock.patch.object(demo, "fill") as fill:
            demo.sign_in()
        fill.assert_not_called()
        self.assertEqual(User.objects.get(pk=user.pk).demo_seeded_at, user.demo_seeded_at)

    def test_regenerates_records_a_week_old_and_keeps_the_same_account(self):
        user = demo.sign_in()
        User.objects.filter(pk=user.pk).update(demo_seeded_at=timezone.now() - timedelta(days=8))
        AssistantUsage.objects.create(user=user, day=timezone.now().date(), questions=3)
        old_session_ids = set(Session.objects.filter(user=user).values_list("id", flat=True))

        again = demo.sign_in()

        # Same id, so visitors already signed in stay signed in.
        self.assertEqual(again.pk, user.pk)
        self.assertGreater(again.demo_seeded_at, timezone.now() - timedelta(minutes=1))
        self.assertFalse(Session.objects.filter(id__in=old_session_ids).exists())
        # Regenerating doesn't hand back the day's AI questions.
        self.assertEqual(AssistantUsage.objects.get(user=user).questions, 3)

    @override_settings(DEMO_ENABLED=False)
    def test_refuses_when_switched_off(self):
        with self.assertRaises(demo.DemoUnavailable):
            demo.sign_in()
        self.assertFalse(User.objects.exists())

    def test_refuses_if_the_demo_email_is_a_real_account(self):
        real = make_real_user(email="demo@tutorhub.test")
        with self.assertRaises(demo.DemoUnavailable):
            demo.sign_in()
        real.refresh_from_db()
        self.assertFalse(real.is_demo)


def _api_views(patterns=None, prefix="", groups=()):
    """Every API view class with the URL kwargs its route captures."""
    for entry in get_resolver().url_patterns if patterns is None else patterns:
        route = prefix + str(entry.pattern)
        names = (*groups, *entry.pattern.regex.groupindex)
        if isinstance(entry, URLResolver):
            yield from _api_views(entry.url_patterns, route, names)
        elif isinstance(entry, URLPattern) and route.lstrip("^").startswith("api/v1/"):
            view_class = getattr(entry.callback, "cls", None)
            if view_class and issubclass(view_class, APIView):
                yield route, entry.callback, view_class, names


class DemoIsReadOnlyTests(APITestCase):
    def setUp(self):
        self.user = demo.get_or_create_user()

    def test_every_api_view_refuses_changes_from_the_demo(self):
        factory = APIRequestFactory()
        checked = 0
        for route, callback, view_class, names in _api_views():
            # Views with no authentication (log in, refresh, setup) never see the demo user.
            if not view_class.authentication_classes or view_class in DEMO_WRITABLE:
                continue
            # The permission check runs before any object lookup, so placeholder ids are enough.
            kwargs = {name: "00000000-0000-0000-0000-000000000000" for name in names}
            if "format" in kwargs:
                kwargs["format"] = "json"
            for method in ("post", "put", "patch", "delete"):
                with self.subTest(route=route, method=method):
                    request = getattr(factory, method)("/", {}, format="json")
                    force_authenticate(request, user=self.user)
                    response = callback(request, **kwargs)
                    if response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED and not hasattr(view_class, method):
                        continue  # A read-only view, like the API docs.
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                    self.assertEqual(response.data["detail"], "This is the read-only demo, so changes can't be saved.")
            checked += 1
        # Guard against the walk silently finding nothing.
        self.assertGreater(checked, 15)

    def test_can_read(self):
        self.client.force_authenticate(self.user)
        demo.fill(self.user)
        response = self.client.get("/api/v1/students/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 9)

    def test_me_says_it_is_the_demo(self):
        self.client.force_authenticate(self.user)
        self.assertTrue(self.client.get("/api/v1/auth/me").json()["is_demo"])

    def test_real_accounts_can_still_make_changes(self):
        self.client.force_authenticate(make_real_user())
        response = self.client.post("/api/v1/students/", {"first_name": "Sam", "last_name": "Smith"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_start_connecting_google(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/v1/calendar/connect").status_code, status.HTTP_403_FORBIDDEN)

    def test_google_callback_wont_attach_an_account_to_the_demo(self):
        state = calendar_services.sign_connect_state(self.user)
        with mock.patch.object(calendar_services, "exchange_code") as exchange:
            response = self.client.get("/api/v1/calendar/callback", {"state": state, "code": "abc"})
        exchange.assert_not_called()
        self.assertEqual(response["Location"], "/app/connections?error=invalid_state")

    def test_first_run_setup_ignores_the_demo_account(self):
        self.assertEqual(self.client.get("/api/v1/setup").json(), {"needed": True})
        make_real_user()
        self.assertEqual(self.client.get("/api/v1/setup").json(), {"needed": False})
