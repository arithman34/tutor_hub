from rest_framework import serializers

from .models import Session


class SessionSerializer(serializers.ModelSerializer):
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Session
        fields = [
            "id",
            "student",
            "session_date",
            "session_start_time",
            "session_end_time",
            "minutes",
            "zoom_meeting_uuid",
            "zoom_summary_raw",
            "work_covered",
            "student_actions",
            "tutor_actions",
            "next_lesson_focus",
            "topic_tags",
            "is_no_show",
            "calendar_event_id",
            "calendar_recurring_id",
            "calendar_html_link",
            "ilp_generated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("session_start_time", getattr(self.instance, "session_start_time", None))
        end = attrs.get("session_end_time", getattr(self.instance, "session_end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError("session_end_time must be after session_start_time")
        return attrs
