from datetime import datetime, timezone

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from . import dashboard
from .serializers import (
    DashboardSerializer,
    FilterOptionsSerializer,
    RevenueByMonthSerializer,
    StudentBreakdownSerializer,
    TrendsQuerySerializer,
    TrendsSerializer,
    UpcomingQuerySerializer,
    UpcomingSessionsSerializer,
)


class TrendsView(APIView):

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

    @extend_schema(summary="Students and payees for the filter bar", responses=FilterOptionsSerializer)
    def get(self, request):
        return Response(services.get_filter_options(request.user.id))


class DashboardView(APIView):

    @extend_schema(summary="Headline numbers for the dashboard", responses=DashboardSerializer)
    def get(self, request):
        return Response(DashboardSerializer(dashboard.get_dashboard_stats(request.user)).data)


class DashboardRevenueView(APIView):

    @extend_schema(summary="Revenue for each of the last 12 months", responses=RevenueByMonthSerializer)
    def get(self, request):
        return Response(RevenueByMonthSerializer({"months": dashboard.get_revenue_by_month(request.user)}).data)


class DashboardUpcomingView(APIView):

    @extend_schema(summary="Sessions today and over the next few days", parameters=[UpcomingQuerySerializer], responses=UpcomingSessionsSerializer)
    def get(self, request):
        query = UpcomingQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        sessions = dashboard.get_upcoming_sessions(request.user, days=query.validated_data["days"])
        return Response(UpcomingSessionsSerializer({"sessions": sessions}).data)


class DashboardStudentsView(APIView):

    @extend_schema(summary="Revenue and hours for each student this month", responses=StudentBreakdownSerializer)
    def get(self, request):
        return Response(StudentBreakdownSerializer({"students": dashboard.get_student_breakdown(request.user)}).data)
