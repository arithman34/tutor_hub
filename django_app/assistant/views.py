"""TutorHub AI over the API.

The conversation is kept in the Django session (see conversation.py), so
the browser app sees the same chat across page loads. API clients that don't
keep the session cookie get a fresh conversation on every request.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import conversation, quota
from .llm import LLMError
from .serializers import AnswerSerializer, AskSerializer, ConversationSerializer


def _allowance(user) -> dict:
    allowance = quota.get_allowance(user)
    return {
        "limit": allowance.limit,
        "used": allowance.used,
        "remaining": allowance.remaining,
        "unlimited": allowance.unlimited,
        "exhausted": allowance.exhausted,
    }


class ConversationView(APIView):

    @extend_schema(summary="The current conversation and today's allowance", responses=ConversationSerializer)
    def get(self, request):
        return Response(
            {
                "history": conversation.get_history(request.session, request.user),
                "allowance": _allowance(request.user),
                "examples": list(conversation.EXAMPLE_QUESTIONS),
                "max_question_length": conversation.MAX_QUESTION_LENGTH,
            }
        )


class AskView(APIView):
    # The chat lives in the visitor's own session; the demo's daily cap limits the cost.
    demo_can_write = True

    @extend_schema(
        summary="Ask TutorHub AI a question",
        request=AskSerializer,
        responses={
            200: AnswerSerializer,
            429: OpenApiResponse(description="Today's question allowance is used up."),
            502: OpenApiResponse(description="The AI provider failed. The question wasn't charged."),
        },
    )
    def post(self, request):
        body = AskSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        try:
            reply = conversation.ask(request.session, request.user, body.validated_data["question"])
        except quota.QuotaExceeded:
            return Response(
                {"detail": "You've used today's TutorHub AI questions.", "allowance": _allowance(request.user)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except LLMError:
            return Response(
                {"detail": "TutorHub AI couldn't answer just now. Try again in a moment."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "reply": reply,
                "history": conversation.get_history(request.session, request.user),
                "allowance": _allowance(request.user),
            }
        )


class ResetView(APIView):
    demo_can_write = True

    @extend_schema(summary="Start a new conversation", request=None, responses={204: None})
    def post(self, request):
        conversation.reset(request.session, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
