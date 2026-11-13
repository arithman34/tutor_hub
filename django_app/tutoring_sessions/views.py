import logging
import uuid
from dataclasses import asdict

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin
from zoom_integration import services as zoom_services

from . import zoom
from .models import Session
from .serializers import SessionSerializer, ZoomFetchedSummarySerializer, ZoomParseSerializer, ZoomSummarySerializer

logger = logging.getLogger(__name__)


class SessionPagination(LimitOffsetPagination):
    default_limit = 20


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Filter by student name."),
            OpenApiParameter("student", OpenApiTypes.UUID, description="Only this student's sessions."),
        ]
    )
)
class SessionViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Session
    serializer_class = SessionSerializer
    pagination_class = SessionPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("student")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
        student = self.request.query_params.get("student")
        if student:
            try:
                qs = qs.filter(student_id=uuid.UUID(student))
            except ValueError:
                return qs.none()
        return qs

    @extend_schema(
        summary="Fill in session notes from a Zoom summary",
        description="Sends the pasted summary to OpenAI and returns the session note fields. Nothing is saved.",
        request=ZoomSummarySerializer,
        responses={200: ZoomParseSerializer, 502: OpenApiResponse(description="The summary couldn't be parsed.")},
    )
    @action(detail=False, methods=["post"], url_path="zoom-parse")
    def zoom_parse(self, request):
        body = ZoomSummarySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            parsed = zoom.parse_zoom_summary(body.validated_data["summary"])
        except Exception:
            logger.exception("Parsing a Zoom summary failed")
            return Response({"detail": "Could not parse the summary."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(ZoomParseSerializer(asdict(parsed)).data)

    @extend_schema(
        summary="Fetch this session's Zoom AI summary",
        description=(
            "Finds the occurrence of the student's Zoom meeting that started closest to this session "
            "(within an hour) and returns its AI Companion summary. Nothing is saved."
        ),
        responses={
            200: ZoomFetchedSummarySerializer,
            404: OpenApiResponse(description="No matching meeting, or no summary for it yet."),
            409: OpenApiResponse(description="Zoom isn't connected, or the connection expired."),
            502: OpenApiResponse(description="Zoom couldn't be reached or returned an error."),
        },
    )
    @action(detail=True, methods=["get"], url_path="zoom-summary")
    def zoom_summary(self, request, pk=None):
        session = self.get_object()
        try:
            meeting_uuid = zoom_services.find_meeting_uuid(request.user, session.student.zoom_meeting_id, session.session_start_time)
            summary = zoom_services.fetch_summary(request.user, meeting_uuid)
        except zoom_services.NotConnectedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except zoom_services.NotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except zoom_services.ZoomAPIError as exc:
            logger.exception("Fetching a Zoom summary failed for session %s", session.id)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"summary": summary, "meeting_uuid": meeting_uuid})
