from rest_framework import serializers


class ZoomConnectUrlSerializer(serializers.Serializer):
    url = serializers.URLField(help_text="Zoom's consent page. Send the browser here.")
