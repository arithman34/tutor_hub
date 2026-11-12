import secrets

from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from . import services
from .models import GoogleCalendarToken
from .serializers import (
    CalendarEventSerializer,
    CalendarSessionsQuerySerializer,
    CalendarSessionsSerializer,
    ConnectionStatusSerializer,
    ConnectUrlSerializer,
    OneOffEventSerializer,
    RecurringEventsSerializer,
)

_STATE_SALT = "calendar-oauth-state"
_STATE_MAX_AGE = 300

_CALENDAR_ERROR = OpenApiResponse(description="Not connected to Google, or Google Calendar couldn't be reached.")


class ConnectView(APIView):
    """Returns the Google OAuth URL for the frontend to redirect the browser to.

    The CSRF `state` isn't a server-side session cookie (this API is JWT-only,
    and the browser hop to Google and back can't carry an Authorization header)
    — instead it's a signed, time-limited token embedding the user id, verified
    in CallbackView.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Start connecting Google Calendar", responses=ConnectUrlSerializer)
    def get(self, request):
        state = signing.dumps({"user_id": str(request.user.id), "nonce": secrets.token_urlsafe(16)}, salt=_STATE_SALT)
        return Response({"url": services.build_connect_url(state)})


class CallbackView(APIView):
    """Google redirects the browser here directly, so no JWT is available —
    identity comes from the signed `state` instead. Redirects back to the
    frontend with a query flag describing the outcome."""

    # Identity comes from `state`, so skip cookie auth: a stale cookie must
    # not turn Google's redirect into a 401.
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Google's OAuth redirect target",
        description="Not called directly. Google sends the browser here, and it redirects on to the frontend.",
        responses={302: None},
    )
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

    @extend_schema(summary="Whether Google Calendar is connected", responses=ConnectionStatusSerializer)
    def get(self, request):
        token = GoogleCalendarToken.objects.filter(user=request.user).first()
        return Response({"connected": bool(token and token.is_connected)})


class DisconnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Disconnect Google Calendar", request=None, responses={204: None})
    def post(self, request):
        token = GoogleCalendarToken.objects.filter(user=request.user).first()
        if token:
            services.disconnect_token(token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpcomingEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Upcoming Tutoring calendar events",
        responses={200: CalendarEventSerializer(many=True), 400: _CALENDAR_ERROR},
    )
    def get(self, request):
        try:
            events = services.get_upcoming_events(request.user)
        except (ValueError, services.CalendarUnreachableError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response([services.parse_event(e) for e in events])


class CalendarSessionsView(APIView):
    """The sessions page: calendar events and whether each has been logged."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Tutoring calendar events with their logged status",
        parameters=[CalendarSessionsQuerySerializer],
        responses={
            200: CalendarSessionsSerializer,
            409: OpenApiResponse(description="Google Calendar was never connected."),
        },
    )
    def get(self, request):
        query = CalendarSessionsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        if not GoogleCalendarToken.objects.filter(user=request.user).exists():
            return Response({"detail": "Google Calendar is not connected."}, status=status.HTTP_409_CONFLICT)

        items, error = services.calendar_session_items(request.user, **query.validated_data)
        return Response(CalendarSessionsSerializer({"items": items, "error": error}).data)


class OneOffEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Book a one-off lesson",
        request=OneOffEventSerializer,
        responses={201: CalendarEventSerializer, 400: _CALENDAR_ERROR},
    )
    def post(self, request):
        body = OneOffEventSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            event = services.create_one_off_event(
                request.user,
                summary=data["summary"],
                date_str=data["date"].isoformat(),
                start_time=data["start_time"],
                end_time=data["end_time"],
                location=data.get("location") or None,
            )
        except (ValueError, services.CalendarUnreachableError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.parse_event(event), status=status.HTTP_201_CREATED)


class RecurringEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Book weekly lessons",
        description="Creates one recurring event per weekday in day_configs.",
        request=RecurringEventsSerializer,
        responses={201: CalendarEventSerializer(many=True), 400: _CALENDAR_ERROR},
    )
    def post(self, request):
        body = RecurringEventsSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            events = services.create_recurring_events(
                request.user,
                summary=data["summary"],
                day_configs=[dict(config) for config in data["day_configs"]],
                start_date_str=data["start_date"].isoformat(),
                end_date_str=data["end_date"].isoformat() if data.get("end_date") else None,
                interval_weeks=data["interval_weeks"],
                location=data.get("location") or None,
            )
        except (ValueError, services.CalendarUnreachableError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response([services.parse_event(e) for e in events], status=status.HTTP_201_CREATED)
