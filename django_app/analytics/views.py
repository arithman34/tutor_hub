from datetime import datetime, timezone

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin

from . import services
from .serializers import TrendsQuerySerializer


class TrendsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        query = TrendsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        now = datetime.now(timezone.utc)
        range_ = data.get("range", "12m")
        earliest = services.get_earliest_activity() if range_ == "all" else None
        preset, window_start, window_end = services.resolve_range(range_, data.get("start"), data.get("end"), earliest, now)

        granularity = data.get("granularity", "month")
        filters = services.Filters(
            start=window_start,
            end=window_end,
            granularity=granularity if granularity in services.GRANULARITIES else "month",
            tutor_id=data.get("tutor_id"),
            student_id=data.get("student_id"),
            payee_id=data.get("payee_id"),
        )
        trends = services.get_trends(filters, now=now)
        return Response({"range": preset, **trends})


class FilterOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response(services.get_filter_options())
