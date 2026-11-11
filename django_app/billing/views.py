from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin

from .models import Payee, Payment
from .serializers import PayeeSerializer, PaymentSerializer
from .services import payee_balance


class PayeeViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Payee
    serializer_class = PayeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return qs

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        payee = self.get_object()
        return Response({"balance": payee_balance(payee)})


class PaymentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Payment
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("payee")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(payee__first_name__icontains=q) | Q(payee__last_name__icontains=q))
        return qs
