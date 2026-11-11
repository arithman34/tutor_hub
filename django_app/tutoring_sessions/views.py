from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.pagination import LimitOffsetPagination

from accounts.ownership import OwnedQuerysetMixin

from .models import Session
from .serializers import SessionSerializer


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
