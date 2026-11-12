import uuid

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin

from .models import Student
from .serializers import StudentSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Filter by student name."),
            OpenApiParameter("payee", OpenApiTypes.UUID, description="Only students this payee pays for."),
        ]
    )
)
class StudentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Student
    serializer_class = StudentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        payee = self.request.query_params.get("payee")
        if payee:
            try:
                qs = qs.filter(payee_id=uuid.UUID(payee))
            except ValueError:
                return qs.none()
        return qs

    @extend_schema(summary="Switch a student between active and inactive", request=None, responses=StudentSerializer)
    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        student = self.get_object()
        student.is_active = not student.is_active
        student.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(student).data)
