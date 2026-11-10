from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "document_type",
            "subject",
            "level",
            "exam_board",
            "student",
            "source_url",
            "uploaded_at",
        ]
        read_only_fields = ["id", "source_url", "uploaded_at"]


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=255)
    document_type = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)
    level = serializers.CharField(max_length=50)
    exam_board = serializers.CharField(max_length=100, required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)


class QuerySerializer(serializers.Serializer):
    question = serializers.CharField()
    document_type = serializers.CharField(required=False, allow_null=True)
    subject = serializers.CharField(required=False, allow_null=True)
    level = serializers.CharField(required=False, allow_null=True)
    exam_board = serializers.CharField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)
