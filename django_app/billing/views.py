from django.db.models import Q, Sum
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from accounts.permissions import IsAdmin

from .models import Payee, Payment
from .serializers import PayeeSerializer, PaymentSerializer


def payee_balance(payee: Payee) -> float:
    """balance = payments received - cost of billable sessions (hours * hourly_rate)."""
    paid = Payment.objects.filter(payee=payee).aggregate(total=Sum("amount"))["total"] or 0

    cost = 0.0
    students = payee.students.filter(hourly_rate__isnull=False)
    for student in students:
        for session in student.sessions.all():
            cost += (session.minutes / 60) * student.hourly_rate

    return round(float(paid) - cost, 2)


class PayeeViewSet(viewsets.ModelViewSet):
    serializer_class = PayeeSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_queryset(self):
        qs = Payee.objects.all()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        payee = self.get_object()
        return Response({"balance": payee_balance(payee)})


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        qs = Payment.objects.select_related("payee")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(payee__first_name__icontains=q) | Q(payee__last_name__icontains=q))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
