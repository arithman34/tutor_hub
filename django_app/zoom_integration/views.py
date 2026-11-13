import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import DEMO_READ_ONLY
from calendar_integration.serializers import ConnectionStatusSerializer

from . import services
from .models import ZoomToken
from .serializers import ZoomConnectUrlSerializer

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
