from rest_framework import serializers

from .models import Payee, Payment


class PayeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payee
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "bank_reference_pattern",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "payee",
            "amount",
            "payment_date",
            "payment_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
