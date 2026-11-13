import re

from rest_framework import serializers

from accounts.ownership import OwnedPrimaryKeyRelatedField
from billing.models import Payee

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    payee_id = OwnedPrimaryKeyRelatedField(source="payee", queryset=Payee.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Student
        fields = [
            "id",
            "payee_id",
            "first_name",
            "last_name",
            "level",
            "hourly_rate",
            "zoom_meeting_id",
            "google_doc_id",
            "onedrive_shared_link",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    def validate_zoom_meeting_id(self, value):
        """Store digits only: Zoom shows IDs as "123 4567 8901", the API uses 12345678901."""
        if value is None:
            return None
        digits = re.sub(r"[\s-]", "", value)
        if not digits:
            return None
        if not re.fullmatch(r"\d{9,11}", digits):
            raise serializers.ValidationError("Enter the 9 to 11 digit meeting ID, like 123 4567 8901.")
        return digits

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()
