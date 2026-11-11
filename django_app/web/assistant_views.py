"""TutorHub AI chat page.

The conversation lives in the Django session, keyed by user id so a shared
browser never shows one account's chat to another. Each question is checked
against the account's daily allowance before the model is called.
"""

import logging

from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from assistant import agent, quota
from assistant.llm import LLMError

from .auth import login_required

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000
EXAMPLE_QUESTIONS = (
    "Does any payee owe me money?",
    "How many sessions did I teach last month?",
    "Summarise last week's classes",
)


def _history_key(user) -> str:
    return f"assistant_history:{user.id}"


def _draft_key(user) -> str:
    return f"assistant_draft:{user.id}"


def _history(request) -> list[dict]:
    return request.session.get(_history_key(request.user), [])


def _back_with_draft(request, question: str, flash: str):
    """Return to the page with `flash`, keeping the unanswered question in the box."""
    request.session[_draft_key(request.user)] = question[:MAX_QUESTION_LENGTH]
    return redirect(f"/assistant?flash={flash}")


@login_required
def assistant_page(request):
    return render(
        request,
        "assistant/index.html",
        {
            "user": request.user,
            "active_page": "assistant",
            "history": _history(request),
            "draft": request.session.pop(_draft_key(request.user), ""),
            "allowance": quota.get_allowance(request.user),
            "examples": EXAMPLE_QUESTIONS,
            "max_question_length": MAX_QUESTION_LENGTH,
            "flash": request.GET.get("flash"),
        },
    )


@login_required
@require_http_methods(["POST"])
def assistant_ask(request):
    question = request.POST.get("question", "").strip()
    if not question:
        return redirect("/assistant")
    if len(question) > MAX_QUESTION_LENGTH:
        return _back_with_draft(request, question, "too_long")

    try:
        day = quota.reserve_question(request.user)
    except quota.QuotaExceeded:
        return _back_with_draft(request, question, "limit")

    history = _history(request)
    try:
        reply = agent.answer(request.user, question, history=history)
    except LLMError:
        logger.exception("TutorHub AI provider error")
        quota.refund_question(request.user, day)
        return _back_with_draft(request, question, "error")
    except Exception:
        quota.refund_question(request.user, day)
        raise

    history = [*history, {"role": "user", "content": question}, {"role": "assistant", "content": reply}]
    request.session[_history_key(request.user)] = agent.trim_history(history)
    return redirect("/assistant")


@login_required
@require_http_methods(["POST"])
def assistant_reset(request):
    request.session.pop(_history_key(request.user), None)
    return redirect("/assistant")
