import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai import ParsedSession, parse_zoom_summary


async def test_parse_zoom_summary():
    payload = {
        "work_covered": "Covered quadratic equations",
        "student_actions": "- Practice 10 problems",
        "tutor_actions": "- Prepare worksheet",
        "next_lesson_focus": "Move on to completing the square",
        "topic_tags": "quadratics, algebra",
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(payload)

    with patch("app.services.ai.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await parse_zoom_summary("Some Zoom summary text")

    assert isinstance(result, ParsedSession)
    assert result.work_covered == "Covered quadratic equations"
    assert result.topic_tags == "quadratics, algebra"
