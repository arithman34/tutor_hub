"""Thin wrapper around the LLM provider.

This is the only module that knows which provider TutorHub AI uses. The rest
of the assistant talks in the provider-neutral types below, so switching
provider means writing another client with the same `chat` method.

Conversation messages are plain dicts in one of three shapes:
    {"role": "user", "content": str}
    {"role": "assistant", "content": str | None, "tool_calls": [ToolCall, ...]}
    {"role": "tool", "tool_call_id": str, "content": str}
"""

from dataclasses import dataclass, field
from typing import Protocol

import openai
from django.conf import settings

# Each attempt gets half the caller's remaining time, so one retry still fits inside it.
MAX_RETRIES = 1


class LLMError(Exception):
    """The provider could not be reached or returned an unusable response."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text exactly as the model produced it; the agent validates it.


@dataclass(frozen=True)
class LLMReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def chat(self, system: str, messages: list[dict], tools: list[dict], timeout: float) -> LLMReply: ...


class OpenAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.model = model or settings.ASSISTANT_MODEL
        self._client = openai.OpenAI(api_key=api_key or settings.OPENAI_API_KEY, max_retries=MAX_RETRIES)

    def chat(self, system: str, messages: list[dict], tools: list[dict], timeout: float) -> LLMReply:
        """One model turn. `timeout` is the total seconds the caller can wait, retries included."""
        try:
            response = self._client.chat.completions.create(
                timeout=timeout / (MAX_RETRIES + 1),
                model=self.model,
                messages=[{"role": "system", "content": system}, *(_to_openai(message) for message in messages)],
                tools=[{"type": "function", "function": spec} for spec in tools],
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"OpenAI request failed: {exc.__class__.__name__}") from exc

        if not response.choices:
            raise LLMError("OpenAI returned no choices.")
        message = response.choices[0].message
        return LLMReply(
            text=message.content,
            tool_calls=[
                ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
                for call in message.tool_calls or []
                if call.type == "function"
            ],
        )


def _to_openai(message: dict) -> dict:
    if message["role"] == "assistant" and message.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                for call in message["tool_calls"]
            ],
        }
    if message["role"] == "tool":
        return {"role": "tool", "tool_call_id": message["tool_call_id"], "content": message["content"]}
    return {"role": message["role"], "content": message["content"]}


def get_client() -> LLMClient:
    return OpenAIClient()
