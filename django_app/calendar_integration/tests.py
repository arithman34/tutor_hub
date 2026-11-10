from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from django.core import signing
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole

from . import services
from .models import GoogleCalendarToken


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=UserRole.TUTOR)


def fake_response(json_data, status_code=200):
    return httpx.Response(status_code, json=json_data, request=httpx.Request("POST", "https://example.com"))


class PureLogicTests(APITestCase):
    def test_build_event_title(self):
        self.assertEqual(services.build_event_title("Sam"), "Sam - Tuition")

    def test_build_connect_url_contains_state_and_client_id(self):
        url = services.build_connect_url("abc123")
        self.assertIn("state=abc123", url)
        self.assertIn("access_type=offline", url)

    def test_build_rrule_without_end_date(self):
        rrule = services.build_rrule(weekday=0, interval_weeks=1)
        self.assertEqual(rrule, "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO")

    def test_build_rrule_with_end_date(self):
        rrule = services.build_rrule(weekday=2, interval_weeks=2, end_date_str="2026-12-31")
        self.assertIn("BYDAY=WE", rrule)
        self.assertIn("UNTIL=20261231T235959Z", rrule)

    def test_parse_event_timed(self):
        event = {
            "id": "evt1",
            "summary": "Sam - Tuition",
            "start": {"dateTime": "2026-06-15T09:00:00+01:00"},
            "end": {"dateTime": "2026-06-15T10:00:00+01:00"},
            "htmlLink": "https://calendar.google.com/evt1",
        }
        parsed = services.parse_event(event)
        self.assertEqual(parsed["student_name"], "Sam")
        self.assertEqual(parsed["date"], "2026-06-15")
        self.assertEqual(parsed["start_time"], "09:00")
        self.assertFalse(parsed["all_day"])

    def test_parse_event_all_day(self):
        event = {"id": "evt2", "summary": "Holiday", "start": {"date": "2026-06-15"}}
        parsed = services.parse_event(event)
        self.assertTrue(parsed["all_day"])
        self.assertEqual(parsed["student_name"], "Holiday")


class TokenModelTests(APITestCase):
    def test_not_connected_without_refresh_token(self):
        user = make_user()
        token = GoogleCalendarToken.objects.create(user=user, access_token="x", expires_at=datetime.now(timezone.utc))
        self.assertFalse(token.is_connected)

    def test_connected_with_refresh_token(self):
        user = make_user()
        token = GoogleCalendarToken.objects.create(
            user=user, access_token="x", refresh_token="r", expires_at=datetime.now(timezone.utc)
        )
        self.assertTrue(token.is_connected)


class ExchangeCodeTests(APITestCase):
    @patch("httpx.Client.post")
    def test_exchange_code_creates_token(self, mock_post):
        mock_post.return_value = fake_response({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
        user = make_user()

        token = services.exchange_code("auth-code", user)

        self.assertEqual(token.access_token, "at")
        self.assertEqual(token.refresh_token, "rt")
        self.assertTrue(token.is_connected)

    @patch("httpx.Client.post")
    def test_exchange_code_keeps_existing_refresh_token_when_absent_from_response(self, mock_post):
        user = make_user()
        GoogleCalendarToken.objects.create(user=user, access_token="old", refresh_token="keep-me", expires_at=datetime.now(timezone.utc))

        mock_post.return_value = fake_response({"access_token": "new-at", "expires_in": 3600})
        token = services.exchange_code("auth-code", user)

        self.assertEqual(token.access_token, "new-at")
        self.assertEqual(token.refresh_token, "keep-me")


class DisconnectTests(APITestCase):
    def test_disconnect_clears_credentials_but_keeps_calendar_id(self):
        user = make_user()
        token = GoogleCalendarToken.objects.create(
            user=user,
            access_token="at",
            refresh_token="rt",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            tutoring_calendar_id="cal-123",
        )
        services.disconnect_token(token)
        token.refresh_from_db()
        self.assertFalse(token.is_connected)
        self.assertEqual(token.tutoring_calendar_id, "cal-123")


class CreateOneOffEventTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.token = GoogleCalendarToken.objects.create(
            user=self.user,
            access_token="at",
            refresh_token="rt",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            tutoring_calendar_id="cal-123",
        )

    @patch("httpx.Client.post")
    def test_creates_event_on_existing_calendar(self, mock_post):
        mock_post.return_value = fake_response({"id": "evt1", "summary": "Sam - Tuition"}, status_code=201)

        event = services.create_one_off_event(self.user, "Sam - Tuition", "2026-06-15", "09:00", "10:00")

        self.assertEqual(event["id"], "evt1")
        mock_post.assert_called_once()

    @patch("httpx.Client.post")
    def test_raises_when_not_connected(self, mock_post):
        self.token.refresh_token = None
        self.token.save()
        with self.assertRaises(ValueError):
            services.create_one_off_event(self.user, "Sam - Tuition", "2026-06-15", "09:00", "10:00")
        mock_post.assert_not_called()


class FetchEventsTests(APITestCase):
    def test_returns_empty_list_when_no_calendar_created_yet(self):
        user = make_user()
        GoogleCalendarToken.objects.create(
            user=user, access_token="at", refresh_token="rt", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        events = services.fetch_events(user, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7))
        self.assertEqual(events, [])

    @patch("httpx.Client.get")
    def test_raises_calendar_unreachable_on_404(self, mock_get):
        user = make_user()
        GoogleCalendarToken.objects.create(
            user=user,
            access_token="at",
            refresh_token="rt",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            tutoring_calendar_id="cal-123",
        )
        mock_get.return_value = fake_response({}, status_code=404)
        with self.assertRaises(services.CalendarUnreachableError):
            services.fetch_events(user, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7))


class ViewTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_connect_requires_auth(self):
        response = self.client.get(reverse("calendar-connect"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_connect_returns_google_oauth_url(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("calendar-connect"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("accounts.google.com", response.data["url"])

    def test_status_reports_not_connected_by_default(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("calendar-status"))
        self.assertEqual(response.data, {"connected": False})

    def test_disconnect_is_idempotent_without_existing_token(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("calendar-disconnect"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_callback_rejects_invalid_state(self):
        response = self.client.get(reverse("calendar-callback"), {"code": "x", "state": "not-a-real-token"})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=invalid_state", response.url)

    def test_callback_rejects_google_error(self):
        response = self.client.get(reverse("calendar-callback"), {"error": "access_denied"})
        self.assertIn("error=access_denied", response.url)

    @patch("calendar_integration.views.services.exchange_code")
    def test_callback_with_valid_state_exchanges_code(self, mock_exchange):
        state = signing.dumps({"user_id": str(self.user.id), "nonce": "n"}, salt="calendar-oauth-state")
        response = self.client.get(reverse("calendar-callback"), {"code": "auth-code", "state": state})
        self.assertIn("connected=1", response.url)
        mock_exchange.assert_called_once()
