from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsAdmin

from .models import Student
from .serializers import StudentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.all() if user.is_admin else Student.objects.filter(user=user)

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return qs

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "toggle_active"):
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        requested_tutor_id = self.request.data.get("tutor_id")
        user_id = requested_tutor_id if requested_tutor_id else self.request.user.id
        serializer.save(user_id=user_id)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        student = self.get_object()
        student.is_active = not student.is_active
        student.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(student).data)
