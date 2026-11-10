from rest_framework import serializers

from billing.models import Payee

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    tutor_id = serializers.UUIDField(source="user_id", read_only=True)
    payee_id = serializers.PrimaryKeyRelatedField(source="payee", queryset=Payee.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Student
        fields = [
            "id",
            "tutor_id",
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

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()
