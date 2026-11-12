from rest_framework import serializers

from accounts.ownership import OwnedPrimaryKeyRelatedField

from .models import Payee, Payment
from .services import payee_balance


class PayeeSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField(
        help_text="Payments received minus the cost of billed sessions. Negative means the payee owes money."
    )
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Payee
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "bank_reference_pattern",
            "balance",
            "student_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_balance(self, payee) -> float:
        # A list view passes every payee's balance in, computed in one batch.
        balances = self.context.get("balances")
        if balances is not None and payee.id in balances:
            return balances[payee.id]
        return payee_balance(payee)

    def get_student_count(self, payee) -> int:
        annotated = getattr(payee, "student_count", None)
        return annotated if annotated is not None else payee.students.count()

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()


class PaymentSerializer(serializers.ModelSerializer):
    payee = OwnedPrimaryKeyRelatedField(queryset=Payee.objects.all())
    payee_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "payee",
            "payee_name",
            "amount",
            "payment_date",
            "payment_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_payee_name(self, payment) -> str:
        return f"{payment.payee.first_name} {payment.payee.last_name}"
