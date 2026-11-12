import logging
from dataclasses import asdict

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin

from . import zoom
from .models import Session
from .serializers import SessionSerializer, ZoomParseRequestSerializer, ZoomParseSerializer

logger = logging.getLogger(__name__)


class SessionPagination(LimitOffsetPagination):
    default_limit = 20


class SessionViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Session
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SessionPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("student")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
        return qs

    @extend_schema(
        summary="Fill in session notes from a Zoom summary",
        description="Sends the pasted summary to OpenAI and returns the session note fields. Nothing is saved.",
        request=ZoomParseRequestSerializer,
        responses={200: ZoomParseSerializer, 502: OpenApiResponse(description="The summary couldn't be parsed.")},
    )
    @action(detail=False, methods=["post"], url_path="zoom-parse")
    def zoom_parse(self, request):
        body = ZoomParseRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            parsed = zoom.parse_zoom_summary(body.validated_data["summary"])
        except Exception:
            logger.exception("Parsing a Zoom summary failed")
            return Response({"detail": "Could not parse the summary."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(ZoomParseSerializer(asdict(parsed)).data)
