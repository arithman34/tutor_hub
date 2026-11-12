from rest_framework import serializers

from . import services

_TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


class ConnectUrlSerializer(serializers.Serializer):
    url = serializers.URLField(help_text="Google's consent page. Send the browser here.")


class ConnectionStatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField()


class CalendarEventSerializer(serializers.Serializer):
    """An event on the Tutoring calendar, flattened by services.parse_event."""

    event_id = serializers.CharField()
    summary = serializers.CharField(allow_blank=True)
    student_name = serializers.CharField(allow_blank=True)
    date = serializers.CharField(help_text="YYYY-MM-DD")
    start_time = serializers.CharField(allow_blank=True, help_text="HH:MM, blank for all-day events")
    end_time = serializers.CharField(allow_blank=True, help_text="HH:MM, blank for all-day events")
    all_day = serializers.BooleanField()
    html_link = serializers.CharField(allow_blank=True)


class CalendarSessionItemSerializer(CalendarEventSerializer):
    logged = serializers.BooleanField(help_text="Whether a Session has been logged for this event.")
    session_id = serializers.UUIDField(allow_null=True)
    student_id = serializers.UUIDField(allow_null=True, help_text="The active student the event title matches, if any.")


class CalendarSessionsQuerySerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=services.SESSION_PERIODS, default="all")
    status = serializers.ChoiceField(choices=services.SESSION_STATUSES, default="all")
    q = serializers.CharField(required=False, allow_blank=True, default="", help_text="Filter by event title.")


class CalendarSessionsSerializer(serializers.Serializer):
    items = CalendarSessionItemSerializer(many=True)
    error = serializers.CharField(allow_null=True, help_text="Set when Google Calendar couldn't be reached.")


class OneOffEventRequestSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=255)
    date = serializers.DateField()
    start_time = serializers.RegexField(_TIME, help_text="HH:MM")
    end_time = serializers.RegexField(_TIME, help_text="HH:MM")
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Must be after the start time."})
        return attrs


class DayConfigSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6, help_text="0 = Monday, 6 = Sunday")
    start = serializers.RegexField(_TIME, help_text="HH:MM")
    end = serializers.RegexField(_TIME, help_text="HH:MM")

    def validate(self, attrs):
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError({"end": "Must be after the start time."})
        return attrs


class RecurringEventsRequestSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=255)
    day_configs = DayConfigSerializer(many=True, allow_empty=False)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    interval_weeks = serializers.IntegerField(min_value=1, max_value=52, default=1)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)

    def validate(self, attrs):
        end_date = attrs.get("end_date")
        if end_date and end_date < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "Must be on or after the start date."})
        return attrs
