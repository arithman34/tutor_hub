"""TutorHub AI chat page. The conversation logic lives in assistant.conversation,
shared with the API, so both show the same chat."""

from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from assistant import conversation, quota
from assistant.llm import LLMError

from .auth import login_required


def _draft_key(user) -> str:
    return f"assistant_draft:{user.id}"


def _back_with_draft(request, question: str, flash: str):
    """Return to the page with `flash`, keeping the unanswered question in the box."""
    request.session[_draft_key(request.user)] = question[: conversation.MAX_QUESTION_LENGTH]
    return redirect(f"/assistant?flash={flash}")


@login_required
def assistant_page(request):
    return render(
        request,
        "assistant/index.html",
        {
            "user": request.user,
            "active_page": "assistant",
            "history": conversation.get_history(request.session, request.user),
            "draft": request.session.pop(_draft_key(request.user), ""),
            "allowance": quota.get_allowance(request.user),
            "examples": conversation.EXAMPLE_QUESTIONS,
            "max_question_length": conversation.MAX_QUESTION_LENGTH,
            "flash": request.GET.get("flash"),
        },
    )


@login_required
@require_http_methods(["POST"])
def assistant_ask(request):
    question = request.POST.get("question", "").strip()
    if not question:
        return redirect("/assistant")

    try:
        conversation.ask(request.session, request.user, question)
    except conversation.QuestionTooLong:
        return _back_with_draft(request, question, "too_long")
    except quota.QuotaExceeded:
        return _back_with_draft(request, question, "limit")
    except LLMError:
        return _back_with_draft(request, question, "error")
    return redirect("/assistant")


@login_required
@require_http_methods(["POST"])
def assistant_reset(request):
    conversation.reset(request.session, request.user)
    return redirect("/assistant")
