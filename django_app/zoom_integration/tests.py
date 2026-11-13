from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from django.core import signing
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from students.models import Student
from tutoring_sessions.models import Session

from . import services
from .models import ZoomToken

SESSION_START = datetime(2026, 11, 12, 16, 0, tzinfo=timezone.utc)


def make_user(email="tutor@example.com", **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def connect(user, expires_in=timedelta(hours=1)):
    return ZoomToken.objects.create(
        user=user, access_token="at", refresh_token="rt", expires_at=datetime.now(timezone.utc) + expires_in
    )


def response(status_code=200, json_data=None, method="GET"):
    return httpx.Response(status_code, json=json_data or {}, request=httpx.Request(method, "https://zoom.us"))


def instance(uuid, start):
    return {"uuid": uuid, "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ")}


@override_settings(ZOOM_CLIENT_ID="cid", ZOOM_CLIENT_SECRET="secret", ZOOM_REDIRECT_URI="http://testserver/api/v1/zoom/callback")
class OAuthTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_connect_url_has_client_redirect_and_state(self):
        query = parse_qs(urlparse(services.build_connect_url("abc")).query)
        self.assertEqual(query["client_id"], ["cid"])
        self.assertEqual(query["redirect_uri"], ["http://testserver/api/v1/zoom/callback"])
        self.assertEqual(query["state"], ["abc"])
        self.assertEqual(query["response_type"], ["code"])

    def test_state_round_trips(self):
        self.assertEqual(services.read_connect_state(services.sign_connect_state(self.user)), str(self.user.id))

    def test_state_rejects_tampering(self):
        with self.assertRaises(signing.BadSignature):
            services.read_connect_state(services.sign_connect_state(self.user) + "x")

    def test_state_is_not_interchangeable_with_google_state(self):
        from calendar_integration import services as google

        with self.assertRaises(signing.BadSignature):
            services.read_connect_state(google.sign_connect_state(self.user))

    @patch("httpx.Client.post")
    def test_exchange_code_uses_basic_auth_and_saves_tokens(self, mock_post):
        mock_post.return_value = response(json_data={"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600}, method="POST")
        services.exchange_code("the-code", self.user)

        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["auth"], ("cid", "secret"))
        self.assertEqual(kwargs["data"]["code"], "the-code")
        self.assertNotIn("client_secret", kwargs["data"])
        token = ZoomToken.objects.get(user=self.user)
        self.assertEqual((token.access_token, token.refresh_token), ("new-at", "new-rt"))

    @patch("httpx.Client.post")
    def test_exchange_code_replaces_an_existing_token(self, mock_post):
        connect(self.user)
        mock_post.return_value = response(json_data={"access_token": "a2", "refresh_token": "r2", "expires_in": 3600}, method="POST")
        services.exchange_code("c", self.user)
        self.assertEqual(ZoomToken.objects.get(user=self.user).refresh_token, "r2")

    @patch("httpx.Client.post")
    def test_valid_token_is_not_refreshed(self, mock_post):
        connect(self.user)
        self.assertEqual(services._access_token(self.user), "at")
        mock_post.assert_not_called()

    @patch("httpx.Client.post")
    def test_refresh_saves_the_rotated_refresh_token(self, mock_post):
        connect(self.user, expires_in=timedelta(minutes=-1))
        mock_post.return_value = response(json_data={"access_token": "at2", "refresh_token": "rt2", "expires_in": 3600}, method="POST")

        self.assertEqual(services._access_token(self.user), "at2")
        self.assertEqual(mock_post.call_args.kwargs["data"], {"grant_type": "refresh_token", "refresh_token": "rt"})
        token = ZoomToken.objects.get(user=self.user)
        self.assertEqual(token.refresh_token, "rt2")
        self.assertGreater(token.expires_at, datetime.now(timezone.utc))

    @patch("httpx.Client.post")
    def test_rejected_refresh_disconnects(self, mock_post):
        connect(self.user, expires_in=timedelta(minutes=-1))
        mock_post.return_value = response(400, {"reason": "Invalid Token!"}, method="POST")
        with self.assertRaises(services.NotConnectedError):
            services._access_token(self.user)
        self.assertFalse(ZoomToken.objects.filter(user=self.user).exists())

    @patch("httpx.Client.post")
    def test_refresh_server_error_keeps_the_token(self, mock_post):
        connect(self.user, expires_in=timedelta(minutes=-1))
        mock_post.return_value = response(500, method="POST")
        with self.assertRaises(services.ZoomAPIError):
            services._access_token(self.user)
        self.assertTrue(ZoomToken.objects.filter(user=self.user).exists())

    def test_not_connected(self):
        with self.assertRaises(services.NotConnectedError):
            services._access_token(self.user)

    @patch("httpx.Client.post")
    def test_disconnect_revokes_and_deletes(self, mock_post):
        connect(self.user)
        mock_post.return_value = response(method="POST")
        services.disconnect(self.user)
        self.assertEqual(mock_post.call_args.kwargs["data"], {"token": "at"})
        self.assertFalse(ZoomToken.objects.filter(user=self.user).exists())

    @patch("httpx.Client.post", side_effect=httpx.ConnectError("down"))
    def test_disconnect_deletes_even_if_revoke_fails(self, _):
        connect(self.user)
        services.disconnect(self.user)
        self.assertFalse(ZoomToken.objects.filter(user=self.user).exists())


class MeetingHelperTests(APITestCase):
    def test_normalize_meeting_id(self):
        self.assertEqual(services.normalize_meeting_id("123 4567 8901"), "12345678901")
        self.assertEqual(services.normalize_meeting_id("123-4567-8901"), "12345678901")
        self.assertEqual(services.normalize_meeting_id(None), "")

    def test_encode_plain_uuid_once(self):
        self.assertEqual(services.encode_meeting_uuid("aB3+cd=="), "aB3%2Bcd%3D%3D")

    def test_encode_uuid_starting_with_slash_twice(self):
        self.assertEqual(services.encode_meeting_uuid("/ajXp112QmuoKj4854875=="), "%252FajXp112QmuoKj4854875%253D%253D")

    def test_encode_uuid_containing_double_slash_twice(self):
        self.assertEqual(services.encode_meeting_uuid("ab//cd"), "ab%252F%252Fcd")

    def test_closest_instance_picks_the_nearest_start(self):
        instances = [
            instance("week-before", SESSION_START - timedelta(days=7)),
            instance("late-start", SESSION_START + timedelta(minutes=9)),
            instance("early-join", SESSION_START - timedelta(minutes=3)),
        ]
        self.assertEqual(services.closest_instance(instances, SESSION_START)["uuid"], "early-join")

    def test_closest_instance_outside_tolerance(self):
        instances = [instance("too-late", SESSION_START + timedelta(minutes=61))]
        self.assertIsNone(services.closest_instance(instances, SESSION_START))

    def test_closest_instance_skips_bad_rows(self):
        instances = [{"uuid": "no-time"}, {"uuid": "bad", "start_time": "nope"}, instance("ok", SESSION_START)]
        self.assertEqual(services.closest_instance(instances, SESSION_START)["uuid"], "ok")

    def test_summary_text_prefers_summary_content(self):
        self.assertEqual(services.summary_text({"summary_content": " ## Lesson\nFractions ", "summary_overview": "old"}), "## Lesson\nFractions")

    def test_summary_text_from_legacy_fields_prefers_edited(self):
        text = services.summary_text(
            {
                "summary_title": "Maths",
                "summary_overview": "Covered fractions.",
                "summary_details": [{"label": "Original", "summary": "unused"}],
                "edited_summary": {"summary_details": [{"label": "Fractions", "summary": "Adding unlike denominators."}], "next_steps": ["Worksheet 4"]},
            }
        )
        self.assertEqual(text, "Maths\n\nOverview\nCovered fractions.\n\nFractions\nAdding unlike denominators.\n\nNext steps\n- Worksheet 4")

    def test_summary_text_empty(self):
        self.assertEqual(services.summary_text({}), "")


class ZoomEndpointTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_status(self):
        self.assertEqual(self.client.get("/api/v1/zoom/status").json(), {"connected": False})
        connect(self.user)
        self.assertEqual(self.client.get("/api/v1/zoom/status").json(), {"connected": True})

    def test_connect_returns_zoom_url(self):
        url = self.client.get("/api/v1/zoom/connect").json()["url"]
        self.assertTrue(url.startswith("https://zoom.us/oauth/authorize?"))

    def test_demo_cannot_connect(self):
        demo = make_user("demo@example.com", is_demo=True)
        self.client.force_authenticate(demo)
        self.assertEqual(self.client.get("/api/v1/zoom/connect").status_code, status.HTTP_403_FORBIDDEN)

    @patch("httpx.Client.post")
    def test_disconnect(self, mock_post):
        connect(self.user)
        mock_post.return_value = response(method="POST")
        self.assertEqual(self.client.post("/api/v1/zoom/disconnect").status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ZoomToken.objects.exists())

    def test_disconnect_when_not_connected(self):
        self.assertEqual(self.client.post("/api/v1/zoom/disconnect").status_code, status.HTTP_204_NO_CONTENT)


class CallbackTests(APITestCase):
    URL = "/api/v1/zoom/callback"

    def setUp(self):
        self.user = make_user()

    def assertRedirectsTo(self, resp, query):
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertTrue(resp["Location"].endswith(f"/connections?provider=zoom&{query}"), resp["Location"])

    def test_denied(self):
        self.assertRedirectsTo(self.client.get(self.URL, {"error": "access_denied"}), "error=access_denied")

    def test_bad_state(self):
        self.assertRedirectsTo(self.client.get(self.URL, {"code": "c", "state": "forged"}), "error=invalid_state")

    def test_demo_state_is_refused(self):
        demo = make_user("demo@example.com", is_demo=True)
        state = services.sign_connect_state(demo)
        self.assertRedirectsTo(self.client.get(self.URL, {"code": "c", "state": state}), "error=invalid_state")

    @patch("zoom_integration.services.exchange_code", side_effect=httpx.HTTPError("boom"))
    def test_exchange_failure(self, _):
        state = services.sign_connect_state(self.user)
        self.assertRedirectsTo(self.client.get(self.URL, {"code": "c", "state": state}), "error=token_exchange_failed")

    @patch("zoom_integration.services.exchange_code")
    def test_success(self, mock_exchange):
        state = services.sign_connect_state(self.user)
        self.assertRedirectsTo(self.client.get(self.URL, {"code": "c", "state": state}), "connected=1")
        mock_exchange.assert_called_once_with("c", self.user)

    @patch("zoom_integration.services.exchange_code")
    def test_ignores_a_stale_auth_cookie(self, _):
        # The browser may carry an expired JWT cookie; it must not turn the redirect into a 401.
        self.client.cookies["access_token"] = "expired"
        state = services.sign_connect_state(self.user)
        self.assertRedirectsTo(self.client.get(self.URL, {"code": "c", "state": state}), "connected=1")


class SessionZoomSummaryTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.student = Student.objects.create(user=self.user, first_name="Sam", last_name="Smith", zoom_meeting_id="123 4567 8901")
        self.session = Session.objects.create(
            user=self.user,
            student=self.student,
            session_date=SESSION_START,
            session_start_time=SESSION_START,
            session_end_time=SESSION_START + timedelta(hours=1),
        )
        self.url = f"/api/v1/sessions/{self.session.id}/zoom-summary/"

    def zoom_get(self, *responses):
        return patch("httpx.Client.get", side_effect=list(responses))

    def test_not_connected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_success(self):
        connect(self.user)
        with self.zoom_get(
            response(json_data={"meetings": [instance("/abc==", SESSION_START + timedelta(minutes=2))]}),
            response(json_data={"summary_content": "Covered fractions."}),
        ) as mock_get:
            resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json(), {"summary": "Covered fractions.", "meeting_uuid": "/abc=="})
        first, second = (call.args[0] for call in mock_get.call_args_list)
        self.assertTrue(first.endswith("/past_meetings/12345678901/instances"))
        self.assertTrue(second.endswith("/meetings/%252Fabc%253D%253D/meeting_summary"))
        self.assertEqual(mock_get.call_args.kwargs["headers"], {"Authorization": "Bearer at"})

    def test_student_without_meeting_id(self):
        connect(self.user)
        self.student.zoom_meeting_id = ""
        self.student.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("no Zoom meeting ID", resp.json()["detail"])

    def test_unknown_meeting_id(self):
        connect(self.user)
        with self.zoom_get(response(404, {"code": 3001})):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_meeting_near_the_session(self):
        connect(self.user)
        with self.zoom_get(response(json_data={"meetings": [instance("x", SESSION_START - timedelta(days=7))]})):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("within an hour", resp.json()["detail"])

    def test_summary_not_ready(self):
        connect(self.user)
        with self.zoom_get(response(json_data={"meetings": [instance("u", SESSION_START)]}), response(404)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("AI summary", resp.json()["detail"])

    def test_zoom_error(self):
        connect(self.user)
        with self.zoom_get(response(500)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_zoom_unreachable(self):
        connect(self.user)
        with patch("httpx.Client.get", side_effect=httpx.ConnectError("down")):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_revoked_access_token(self):
        connect(self.user)
        with self.zoom_get(response(401)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_other_users_session(self):
        other = make_user("other@example.com")
        self.client.force_authenticate(other)
        connect(other)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
