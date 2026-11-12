from rest_framework import serializers

from .conversation import MAX_QUESTION_LENGTH


class AllowanceSerializer(serializers.Serializer):
    limit = serializers.IntegerField(allow_null=True, help_text="Questions per day (UK time). Null means unlimited.")
    used = serializers.IntegerField()
    remaining = serializers.IntegerField(allow_null=True)
    unlimited = serializers.BooleanField()
    exhausted = serializers.BooleanField()


class MessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()


class ConversationSerializer(serializers.Serializer):
    history = MessageSerializer(many=True)
    allowance = AllowanceSerializer()
    examples = serializers.ListField(child=serializers.CharField(), help_text="Suggested first questions.")
    max_question_length = serializers.IntegerField()


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH)


class AnswerSerializer(serializers.Serializer):
    reply = serializers.CharField()
    history = MessageSerializer(many=True)
    allowance = AllowanceSerializer()
