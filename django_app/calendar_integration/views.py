import secrets

from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from . import services
from .models import GoogleCalendarToken

_STATE_SALT = "calendar-oauth-state"
_STATE_MAX_AGE = 300


class ConnectView(APIView):
    """Returns the Google OAuth URL for the frontend to redirect the browser to.

    The CSRF `state` isn't a server-side session cookie (this API is JWT-only,
    and the browser hop to Google and back can't carry an Authorization header)
    — instead it's a signed, time-limited token embedding the user id, verified
    in CallbackView.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        state = signing.dumps({"user_id": str(request.user.id), "nonce": secrets.token_urlsafe(16)}, salt=_STATE_SALT)
        return Response({"url": services.build_connect_url(state)})


class CallbackView(APIView):
    """Google redirects the browser here directly, so no JWT is available —
    identity comes from the signed `state` instead. Redirects back to the
    frontend with a query flag describing the outcome."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        error = request.query_params.get("error")
        if error:
            return redirect(f"{settings.FRONTEND_URL}/connections?error=access_denied")

        state = request.query_params.get("state", "")
        try:
            payload = signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
            user = User.objects.get(id=payload["user_id"])
        except (signing.BadSignature, User.DoesNotExist):
            return redirect(f"{settings.FRONTEND_URL}/connections?error=invalid_state")

        try:
            services.exchange_code(request.query_params.get("code", ""), user)
        except Exception:
            return redirect(f"{settings.FRONTEND_URL}/connections?error=token_exchange_failed")

        return redirect(f"{settings.FRONTEND_URL}/connections?connected=1")


class StatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        token = GoogleCalendarToken.objects.filter(user=request.user).first()
        return Response({"connected": bool(token and token.is_connected)})


class DisconnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = GoogleCalendarToken.objects.filter(user=request.user).first()
        if token:
            services.disconnect_token(token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpcomingEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            events = services.get_upcoming_events(request.user)
        except (ValueError, services.CalendarUnreachableError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response([services.parse_event(e) for e in events])


class OneOffEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            event = services.create_one_off_event(
                request.user,
                summary=data["summary"],
                date_str=data["date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                location=data.get("location"),
            )
        except (KeyError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.parse_event(event), status=status.HTTP_201_CREATED)


class RecurringEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            events = services.create_recurring_events(
                request.user,
                summary=data["summary"],
                day_configs=data["day_configs"],
                start_date_str=data["start_date"],
                end_date_str=data.get("end_date"),
                interval_weeks=data.get("interval_weeks", 1),
                location=data.get("location"),
            )
        except (KeyError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response([services.parse_event(e) for e in events], status=status.HTTP_201_CREATED)
