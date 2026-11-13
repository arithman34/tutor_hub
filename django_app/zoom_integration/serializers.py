from rest_framework import serializers


class ZoomConnectUrlSerializer(serializers.Serializer):
    url = serializers.URLField(help_text="Zoom's consent page. Send the browser here.")


class SweepResultSerializer(serializers.Serializer):
    logged = serializers.IntegerField(help_text="Lessons logged as new sessions.")
    updated = serializers.IntegerField(help_text="Sessions already logged that got notes or a summary.")
    waiting = serializers.IntegerField(help_text="Lessons Zoom hasn't finished with yet; tried again next time.")
    failed = serializers.IntegerField(help_text="Lessons given up on after repeated errors.")
