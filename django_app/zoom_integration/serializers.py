from rest_framework import serializers


class ZoomConnectUrlSerializer(serializers.Serializer):
    url = serializers.URLField(help_text="Zoom's consent page. Send the browser here.")


OUTCOME_CHOICES = ["logged", "no_show", "notes_filled", "linked"]


class SweptSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    student_name = serializers.CharField()
    start = serializers.DateTimeField(help_text="Wall-clock, like session_start_time.")
    outcome = serializers.ChoiceField(choices=OUTCOME_CHOICES)


class SweepResultSerializer(serializers.Serializer):
    logged = serializers.IntegerField(help_text="Lessons logged as new sessions.")
    no_shows = serializers.IntegerField(help_text="No-shows logged as new sessions.")
    notes_filled = serializers.IntegerField(help_text="Sessions already logged whose empty notes were filled.")
    linked = serializers.IntegerField(help_text="Sessions already logged that kept their notes; only the summary was stored.")
    waiting = serializers.IntegerField(help_text="Lessons Zoom hasn't finished with yet; tried again next time.")
    failed = serializers.IntegerField(help_text="Lessons given up on after repeated errors.")
    sessions = SweptSessionSerializer(many=True, help_text="The sessions this run logged or changed, newest first.")
