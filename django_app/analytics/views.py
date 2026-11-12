from datetime import datetime, timezone

from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .dashboard import get_dashboard_stats
from .serializers import DashboardSerializer, FilterOptionsSerializer, TrendsQuerySerializer, TrendsSerializer


class TrendsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Charts for the analytics page", parameters=[TrendsQuerySerializer], responses=TrendsSerializer)
    def get(self, request):
        query = TrendsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        now = datetime.now(timezone.utc)
        range_ = data.get("range", "12m")
        earliest = services.get_earliest_activity(request.user.id) if range_ == "all" else None
        preset, window_start, window_end = services.resolve_range(range_, data.get("start"), data.get("end"), earliest, now)

        granularity = data.get("granularity", "month")
        filters = services.Filters(
            start=window_start,
            end=window_end,
            user_id=request.user.id,
            granularity=granularity if granularity in services.GRANULARITIES else "month",
            student_id=data.get("student_id"),
            payee_id=data.get("payee_id"),
        )
        trends = services.get_trends(filters, now=now)
        return Response({"range": preset, **trends})


class FilterOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Students and payees for the filter bar", responses=FilterOptionsSerializer)
    def get(self, request):
        return Response(services.get_filter_options(request.user.id))


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Headline numbers for the dashboard", responses=DashboardSerializer)
    def get(self, request):
        return Response(DashboardSerializer(get_dashboard_stats(request.user)).data)
