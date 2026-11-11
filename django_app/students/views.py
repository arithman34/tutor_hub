from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin

from .models import Student
from .serializers import StudentSerializer


class StudentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Student
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return qs

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        student = self.get_object()
        student.is_active = not student.is_active
        student.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(student).data)
