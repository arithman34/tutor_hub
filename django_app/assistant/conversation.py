"""A TutorHub AI conversation.

The conversation lives in the Django session, keyed by user id so a shared
browser never shows one account's chat to another. Each question is charged
against the account's daily allowance before the model is called, and
refunded if the model fails.
"""

import logging

from . import agent, quota
from .llm import LLMError

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000
EXAMPLE_QUESTIONS = (
    "Does any payee owe me money?",
    "How many sessions did I teach last month?",
    "Summarise last week's classes",
)


class QuestionTooLong(Exception):
    pass


def _history_key(user) -> str:
    return f"assistant_history:{user.id}"


def get_history(session, user) -> list[dict]:
    return session.get(_history_key(user), [])


def reset(session, user) -> None:
    session.pop(_history_key(user), None)


def ask(session, user, question: str) -> str:
    """Answer `question` and append the turn to the conversation.

    Raises QuestionTooLong, quota.QuotaExceeded, or LLMError (after refunding
    the question). The conversation only changes when an answer comes back.
    """
    if len(question) > MAX_QUESTION_LENGTH:
        raise QuestionTooLong

    day = quota.reserve_question(user)
    history = get_history(session, user)
    try:
        reply = agent.answer(user, question, history=history)
    except LLMError:
        logger.exception("TutorHub AI provider error")
        quota.refund_question(user, day)
        raise
    except Exception:
        quota.refund_question(user, day)
        raise

    history = [*history, {"role": "user", "content": question}, {"role": "assistant", "content": reply}]
    session[_history_key(user)] = agent.trim_history(history)
    return reply
