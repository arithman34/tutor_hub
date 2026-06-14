import json
from dataclasses import dataclass

from openai import AsyncOpenAI, DefaultAioHttpClient

from app.core.config import settings


@dataclass
class ParsedSession:
    work_covered: str
    student_actions: str
    tutor_actions: str
    next_lesson_focus: str
    topic_tags: str


_SYSTEM_PROMPT = """\
You are an assistant that extracts structured session notes from a Zoom AI meeting summary.
Return a JSON object with exactly these keys:
  work_covered       — a concise paragraph of what was taught/discussed
  student_actions    — bullet points of tasks the student should do before next session
  tutor_actions      — bullet points of tasks the tutor should do before next session
  next_lesson_focus  — one or two sentences on what to cover next
  topic_tags         — a comma-separated list of short topic keywords (e.g. "binary search, Big O, stacks")

Be concise. Use plain text, not markdown. For bullet points use a dash prefix on each line.
Do not add any extra keys or commentary. If a field is empty, return an empty string for that field.
"""


async def parse_zoom_summary(raw_summary: str) -> ParsedSession:
    async with AsyncOpenAI(api_key=settings.openai_api_key, http_client=DefaultAioHttpClient()) as client:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": raw_summary},
            ],
        )
    data = json.loads(response.choices[0].message.content)
    return ParsedSession(**data)
