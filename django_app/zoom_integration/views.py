import json
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import DEMO_READ_ONLY
from calendar_integration.serializers import ConnectionStatusSerializer

from . import autolog, services, webhook
from .models import ZoomToken
from .serializers import SweepResultSerializer, ZoomConnectUrlSerializer

logger = logging.getLogger(__name__)


def _back_to_connections(**params):
    return redirect(f"{settings.FRONTEND_URL}/connections?{urlencode({'provider': 'zoom', **params})}")


class ConnectView(APIView):
    """Returns Zoom's OAuth URL for the frontend to send the browser to.
    See calendar_integration.views.ConnectView for why `state` is signed."""

    @extend_schema(summary="Start connecting Zoom", responses=ZoomConnectUrlSerializer)
    def get(self, request):
        if request.user.is_demo:
            # A GET, so DemoIsReadOnly lets it through, but connecting would change the account.
            raise PermissionDenied(DEMO_READ_ONLY)
        return Response({"url": services.build_connect_url(services.sign_connect_state(request.user))})


class CallbackView(APIView):
    """Zoom redirects the browser here directly, so identity comes from the
    signed `state`, not a JWT. Redirects on to the Connections page."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Zoom's OAuth redirect target",
        description="Not called directly. Zoom sends the browser here, and it redirects on to the frontend.",
        responses={302: None},
    )
    def get(self, request):
        if request.query_params.get("error"):
            return _back_to_connections(error="access_denied")

        try:
            user = User.objects.get(id=services.read_connect_state(request.query_params.get("state", "")), is_demo=False)
        except (signing.BadSignature, User.DoesNotExist):
            return _back_to_connections(error="invalid_state")

        try:
            services.exchange_code(request.query_params.get("code", ""), user)
        except Exception:
            logger.exception("Zoom token exchange failed for user %s", user.id)
            return _back_to_connections(error="token_exchange_failed")

        return _back_to_connections(connected="1")


class StatusView(APIView):
    @extend_schema(summary="Whether Zoom is connected", responses=ConnectionStatusSerializer)
    def get(self, request):
        return Response({"connected": ZoomToken.objects.filter(user=request.user).exists()})


class DisconnectView(APIView):
    @extend_schema(summary="Disconnect Zoom", request=None, responses={204: None})
    def post(self, request):
        services.disconnect(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookView(APIView):
    """Zoom's event notifications. Signed with the app's Secret Token, which is
    the only proof a request came from Zoom, so anything unsigned is refused."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(exclude=True)
    def post(self, request):
        body = request.body
        if not webhook.is_valid_signature(body, request.headers.get("x-zm-request-timestamp"), request.headers.get("x-zm-signature")):
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(body)
        except ValueError:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get("event")
        if event_type == "endpoint.url_validation":
            plain_token = (payload.get("payload") or {}).get("plainToken", "")
            return JsonResponse(webhook.url_validation_response(plain_token))
        if event_type == "meeting.summary_completed":
            event = webhook.record_summary_event(payload)
            if event:
                autolog.dispatch(event.id)
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)


class SweepView(APIView):
    @extend_schema(
        summary="Log missed Zoom lessons",
        description=(
            "Finds lessons from the last week that Zoom held but TutorHub hasn't logged (including no-shows), "
            "logs them, and retries any still waiting for Zoom."
        ),
        request=None,
        responses={200: SweepResultSerializer, 409: None, 424: None},
    )
    def post(self, request):
        try:
            counts = autolog.sweep(request.user)
        except services.NotConnectedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except services.ZoomAPIError as exc:
            # 424, not 502: Cloudflare swaps an origin's 502 for its own error page, losing the message.
            return Response({"detail": str(exc)}, status=status.HTTP_424_FAILED_DEPENDENCY)
        return Response(counts)
