"""The TutorHub AI tool-calling loop.

The model never sees the database directly: it asks for read-only tools from
`assistant.tools`, the loop runs them for the signed-in user, and the model
answers from what they return. The loop is capped so a confused model cannot
call tools forever.
"""

import json
import logging
from datetime import datetime

from django.utils import timezone

from .llm import LLMClient, LLMReply, get_client
from .tools import LONDON, TOOL_SPECS, run_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_TURNS = 10

GAVE_UP_ANSWER = "Sorry, I couldn't work that out. Try asking a narrower question, for example about one student or one month."
EMPTY_ANSWER = "Sorry, I don't have an answer for that."

_SYSTEM_PROMPT = """\
You are TutorHub AI, an assistant for a private tutor in the UK. You answer questions about the \
tutor's own students, tutoring sessions, payees (the people who pay for lessons) and payments.

Today is {today}. Interpret relative dates such as "last week" or "this month" in UK time, and \
pass dates to tools as YYYY-MM-DD. Weeks run Monday to Sunday.

Rules:
- Answer only from tool results. If the tools do not return what you need, say you don't know. Never guess numbers, names or dates.
- To refer to a student by name, call find_students first to get their id. If more than one student matches, ask which one the tutor means.
- A negative payee balance means the payee owes that amount; positive means they are in credit. Money is in GBP (£).
- You can only read data. If asked to change anything, say you can't and point the tutor to the relevant page in TutorHub.
- Never show ids to the tutor.
- Reply in plain text, without markdown, and keep it brief.
"""


def build_system_prompt(now: datetime | None = None) -> str:
    today = (now or timezone.now()).astimezone(LONDON)
    return _SYSTEM_PROMPT.format(today=f"{today:%A} {today.day} {today:%B %Y}")


def trim_history(history: list[dict]) -> list[dict]:
    """The last MAX_HISTORY_TURNS question/answer pairs, as plain user/assistant text messages."""
    messages = [
        {"role": message["role"], "content": message["content"]}
        for message in history
        if message.get("role") in ("user", "assistant") and isinstance(message.get("content"), str)
    ]
    return messages[-2 * MAX_HISTORY_TURNS :]


def answer(user, question: str, history: list[dict] | None = None, client: LLMClient | None = None, now: datetime | None = None) -> str:
    """Answer `question` for `user`, given earlier user/assistant turns.

    Raises `assistant.llm.LLMError` if the provider fails; callers decide how to show that.
    """
    client = client or get_client()
    system = build_system_prompt(now)
    messages = [*trim_history(history or []), {"role": "user", "content": question}]

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        reply = client.chat(system, messages, TOOL_SPECS)
        if not reply.tool_calls:
            return (reply.text or "").strip() or EMPTY_ANSWER

        logger.info("assistant round %d: %s", round_number, ", ".join(call.name for call in reply.tool_calls))
        messages.append({"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls})
        messages.extend(_run_tool_calls(user, reply))

    logger.warning("assistant gave up after %d tool rounds", MAX_TOOL_ROUNDS)
    return GAVE_UP_ANSWER


def _run_tool_calls(user, reply: LLMReply) -> list[dict]:
    results = []
    for call in reply.tool_calls:
        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            result = {"error": "Arguments were not valid JSON."}
        else:
            result = run_tool(user, call.name, arguments)
        results.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    return results
