from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.pagination import LimitOffsetPagination

from .models import Session
from .serializers import SessionSerializer


class SessionPagination(LimitOffsetPagination):
    default_limit = 20


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SessionPagination

    def get_queryset(self):
        user = self.request.user
        qs = Session.objects.select_related("student") if user.is_admin else Session.objects.filter(user=user)

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
