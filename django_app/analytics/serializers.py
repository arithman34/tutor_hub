from rest_framework import serializers


class TrendsQuerySerializer(serializers.Serializer):
    range = serializers.CharField(required=False, default="12m")
    granularity = serializers.CharField(required=False, default="month")
    start = serializers.DateField(required=False, allow_null=True)
    end = serializers.DateField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)
    payee_id = serializers.UUIDField(required=False, allow_null=True)
