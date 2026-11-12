import uuid

from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from accounts.ownership import OwnedQuerysetMixin

from .models import Payee, Payment
from .serializers import PayeeSerializer, PaymentSerializer
from .services import payee_balance, payee_balances


@extend_schema_view(list=extend_schema(parameters=[OpenApiParameter("q", str, description="Filter by payee name.")]))
class PayeeViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Payee
    serializer_class = PayeeSerializer

    def get_queryset(self):
        qs = super().get_queryset().annotate(student_count=Count("students"))
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return qs

    def list(self, request, *args, **kwargs):
        # Every payee's balance in two queries, rather than two per payee.
        payees = list(self.filter_queryset(self.get_queryset()))
        context = {**self.get_serializer_context(), "balances": payee_balances(payees)}
        return Response(self.get_serializer_class()(payees, many=True, context=context).data)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        payee = self.get_object()
        return Response({"balance": payee_balance(payee)})


class PaymentPagination(LimitOffsetPagination):
    # Without a default, LimitOffsetPagination only pages when the client
    # sends ?limit= and otherwise returns a bare list, which isn't the shape
    # the schema documents.
    default_limit = 20


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Filter by payee name."),
            OpenApiParameter("payee", OpenApiTypes.UUID, description="Only this payee's payments."),
        ]
    )
)
class PaymentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    model = Payment
    serializer_class = PaymentSerializer
    pagination_class = PaymentPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("payee")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(payee__first_name__icontains=q) | Q(payee__last_name__icontains=q))
        payee = self.request.query_params.get("payee")
        if payee:
            try:
                qs = qs.filter(payee_id=uuid.UUID(payee))
            except ValueError:
                return qs.none()
        return qs
