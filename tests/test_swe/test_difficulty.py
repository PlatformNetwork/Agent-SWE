"""Tests for difficulty classifier."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from swe_forge.llm import (
    Choice,
    GenerationResponse,
    Message,
    ToolCall,
    Usage,
)
from swe_forge.llm.client import FunctionCall
from swe_forge.swe.difficulty import (
    CLASSIFY_TOOL_SCHEMA,
    TRIAGE_TOOL_SCHEMA,
    ClassifyResponse,
    DifficultyClassifier,
    DifficultyLevel,
    PRInfo,
    TaskInfo,
    TriageResponse,
    clamp_score,
    get_score_for_difficulty,
    score_to_difficulty,
)


class TestDifficultyLevel:
    def test_values(self):
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.MEDIUM.value == "medium"
        assert DifficultyLevel.HARD.value == "hard"


class TestClampScore:
    def test_clamp_below_range(self):
        assert clamp_score(-0.5) == 0.0

    def test_clamp_above_range(self):
        assert clamp_score(1.5) == 1.0

    def test_clamp_in_range(self):
        assert clamp_score(0.5) == 0.5

    def test_clamp_boundaries(self):
        assert clamp_score(0.0) == 0.0
        assert clamp_score(1.0) == 1.0


class TestScoreToDifficulty:
    def test_easy_threshold(self):
        assert score_to_difficulty(0.1) == "easy"
        assert score_to_difficulty(0.35) == "easy"

    def test_medium_threshold(self):
        assert score_to_difficulty(0.4) == "medium"
        assert score_to_difficulty(0.65) == "medium"

    def test_hard_threshold(self):
        assert score_to_difficulty(0.7) == "hard"
        assert score_to_difficulty(1.0) == "hard"


class TestGetScoreForDifficulty:
    def test_easy_midpoint(self):
        score = get_score_for_difficulty("easy")
        assert 0.1 <= score <= 0.35
        assert abs(score - 0.225) < 0.001  # (0.1 + 0.35) / 2

    def test_medium_midpoint(self):
        score = get_score_for_difficulty("medium")
        assert 0.4 <= score <= 0.65
        assert score == 0.525  # (0.4 + 0.65) / 2

    def test_hard_midpoint(self):
        score = get_score_for_difficulty("hard")
        assert 0.7 <= score <= 1.0
        assert score == 0.85  # (0.7 + 1.0) / 2


class TestPRInfo:
    def test_truncated_body_short(self):
        pr = PRInfo(title="Test", body="Short text")
        assert pr.truncated_body() == "Short text"

    def test_truncated_body_long(self):
        long_body = "x" * 2000
        pr = PRInfo(title="Test", body=long_body)
        result = pr.truncated_body(1000)
        assert len(result) == 1003  # 1000 + "..."
        assert result.endswith("...")

    def test_truncated_body_custom_max(self):
        pr = PRInfo(title="Test", body="x" * 100)
        result = pr.truncated_body(50)
        assert len(result) == 53
        assert result.endswith("...")


class TestTaskInfo:
    def test_create_task_info(self):
        pr_info = PRInfo(title="Fix bug", body="Body")
        task = TaskInfo(
            pr_info=pr_info,
            files_changed=3,
            lines_added=50,
            lines_removed=20,
            file_paths=["a.py", "b.py", "c.py"],
        )
        assert task.files_changed == 3
        assert task.lines_added == 50
        assert task.lines_removed == 20
        assert len(task.file_paths) == 3


def make_tool_response(tool_name: str, args: dict) -> GenerationResponse:
    tool_call = ToolCall(
        id="call_123",
        type="function",
        function=FunctionCall(name=tool_name, arguments=json.dumps(args)),
    )
    message = Message.assistant_with_tool_calls("", [tool_call])
    choice = Choice(index=0, message=message, finish_reason="tool_calls")
    return GenerationResponse(
        id="resp_123",
        model="test-model",
        choices=[choice],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def make_text_response(content: str) -> GenerationResponse:
    message = Message.assistant(content)
    choice = Choice(index=0, message=message, finish_reason="stop")
    return GenerationResponse(
        id="resp_123",
        model="test-model",
        choices=[choice],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class TestDifficultyClassifierTriage:
    @pytest.mark.asyncio
    async def test_triage_easy(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "triage",
                {"difficulty": "easy", "reasoning": "Simple doc fix"},
            )
        )

        classifier = DifficultyClassifier(mock_client, model="test-model")
        pr_info = PRInfo(title="Fix typo in README", body="Fixed a typo")

        result = await classifier.classify_triage(pr_info)

        assert isinstance(result, TriageResponse)
        assert result.difficulty == "easy"
        assert result.reasoning == "Simple doc fix"

    @pytest.mark.asyncio
    async def test_triage_medium(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "triage",
                {"difficulty": "medium", "reasoning": "Bug fix with test"},
            )
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Fix null pointer in handler", body="Add null check")

        result = await classifier.classify_triage(pr_info)

        assert result.difficulty == "medium"
        assert result.reasoning == "Bug fix with test"

    @pytest.mark.asyncio
    async def test_triage_hard(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "triage",
                {"difficulty": "hard", "reasoning": "Major refactor of auth module"},
            )
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Refactor authentication system", body="Large changes")

        result = await classifier.classify_triage(pr_info)

        assert result.difficulty == "hard"

    @pytest.mark.asyncio
    async def test_triage_json_fallback(self):
        json_content = '{"difficulty": "medium", "reasoning": "Fallback parsed"}'
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_text_response(json_content)
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Test", body="Body")

        result = await classifier.classify_triage(pr_info)

        assert result.difficulty == "medium"
        assert "Fallback" in result.reasoning

    @pytest.mark.asyncio
    async def test_triage_error_defaults_to_medium(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(side_effect=Exception("API error"))

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Test", body="Body")

        result = await classifier.classify_triage(pr_info)

        assert result.difficulty == "medium"
        assert "Error" in result.reasoning

    @pytest.mark.asyncio
    async def test_triage_no_tool_call_defaults_to_medium(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_text_response("No tool calls here")
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Test", body="Body")

        result = await classifier.classify_triage(pr_info)

        assert result.difficulty == "medium"
        assert "Failed to parse" in result.reasoning


class TestDifficultyClassifierFull:
    @pytest.mark.asyncio
    async def test_classify_full_easy(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "classify_pr",
                {
                    "difficulty": "easy",
                    "score": 0.2,
                    "quality_good": True,
                    "reasoning": "Small doc change",
                },
            )
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Fix typo", body="Typo fix")
        task_info = TaskInfo(
            pr_info=pr_info,
            files_changed=1,
            lines_added=5,
            lines_removed=2,
            file_paths=["README.md"],
        )

        result = await classifier.classify_full(task_info)

        assert isinstance(result, ClassifyResponse)
        assert result.difficulty == "easy"
        assert result.score == 0.2
        assert result.quality_good is True
        assert result.reasoning == "Small doc change"

    @pytest.mark.asyncio
    async def test_classify_full_hard(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "classify_pr",
                {
                    "difficulty": "hard",
                    "score": 0.85,
                    "quality_good": False,
                    "reasoning": "Complex security refactor",
                },
            )
        )

        classifier = DifficultyClassifier(mock_client)
        pr_info = PRInfo(title="Security refactor", body="Major changes")
        task_info = TaskInfo(
            pr_info=pr_info,
            files_changed=8,
            lines_added=500,
            lines_removed=300,
            file_paths=["auth.py", "security.py", "session.py"],
        )

        result = await classifier.classify_full(task_info)

        assert result.difficulty == "hard"
        assert result.score == 0.85
        assert result.quality_good is False

    @pytest.mark.asyncio
    async def test_classify_clamps_score(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "classify_pr",
                {
                    "difficulty": "hard",
                    "score": 2.5,  # Out of range
                    "quality_good": True,
                    "reasoning": "Test",
                },
            )
        )

        classifier = DifficultyClassifier(mock_client)
        task_info = TaskInfo(
            pr_info=PRInfo(title="Test", body="Body"),
            files_changed=1,
            lines_added=10,
            lines_removed=5,
            file_paths=["test.py"],
        )

        result = await classifier.classify_full(task_info)

        assert result.score == 1.0  # Clamped

    @pytest.mark.asyncio
    async def test_classify_clamps_negative_score(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "classify_pr",
                {
                    "difficulty": "easy",
                    "score": -0.5,  # Negative
                    "quality_good": True,
                    "reasoning": "Test",
                },
            )
        )

        classifier = DifficultyClassifier(mock_client)
        task_info = TaskInfo(
            pr_info=PRInfo(title="Test", body="Body"),
            files_changed=1,
            lines_added=10,
            lines_removed=5,
            file_paths=["test.py"],
        )

        result = await classifier.classify_full(task_info)

        assert result.score == 0.0  # Clamped

    @pytest.mark.asyncio
    async def test_classify_json_fallback(self):
        json_content = '{"difficulty": "medium", "score": 0.45, "quality_good": false, "reasoning": "Fallback"}'
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_text_response(json_content)
        )

        classifier = DifficultyClassifier(mock_client)
        task_info = TaskInfo(
            pr_info=PRInfo(title="Test", body="Body"),
            files_changed=2,
            lines_added=30,
            lines_removed=15,
            file_paths=["a.py", "b.py"],
        )

        result = await classifier.classify_full(task_info)

        assert result.difficulty == "medium"
        assert result.score == 0.45
        assert result.quality_good is False

    @pytest.mark.asyncio
    async def test_classify_error_defaults_to_medium(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(side_effect=Exception("API error"))

        classifier = DifficultyClassifier(mock_client)
        task_info = TaskInfo(
            pr_info=PRInfo(title="Test", body="Body"),
            files_changed=1,
            lines_added=10,
            lines_removed=5,
            file_paths=["test.py"],
        )

        result = await classifier.classify_full(task_info)

        assert result.difficulty == "medium"
        assert result.score == 0.5
        assert result.quality_good is False
        assert "Error" in result.reasoning

    @pytest.mark.asyncio
    async def test_classify_includes_diff_preview(self):
        mock_client = MagicMock(spec=["complete_with_tools"])
        mock_client.complete_with_tools = AsyncMock(
            return_value=make_tool_response(
                "classify_pr",
                {
                    "difficulty": "medium",
                    "score": 0.5,
                    "quality_good": True,
                    "reasoning": "Test",
                },
            )
        )

        classifier = DifficultyClassifier(mock_client)
        task_info = TaskInfo(
            pr_info=PRInfo(title="Test", body="Body"),
            files_changed=1,
            lines_added=10,
            lines_removed=5,
            file_paths=["test.py"],
            diff_preview="def foo():\n    pass",
        )

        result = await classifier.classify_full(task_info)

        assert result.difficulty == "medium"
        # Verify the diff_preview was passed to the request
        call_args = mock_client.complete_with_tools.call_args
        request = call_args[0][0]
        user_msg = request.messages[1].content
        assert "Diff preview:" in user_msg


class TestToolSchemas:
    def test_triage_schema_structure(self):
        assert TRIAGE_TOOL_SCHEMA["name"] == "triage"
        props = TRIAGE_TOOL_SCHEMA["parameters"]["properties"]
        assert "difficulty" in props
        assert "reasoning" in props
        assert props["difficulty"]["enum"] == ["easy", "medium", "hard"]

    def test_classify_schema_structure(self):
        assert CLASSIFY_TOOL_SCHEMA["name"] == "classify_pr"
        props = CLASSIFY_TOOL_SCHEMA["parameters"]["properties"]
        assert "difficulty" in props
        assert "score" in props
        assert "quality_good" in props
        assert "reasoning" in props
        assert props["score"]["type"] == "number"
        assert props["quality_good"]["type"] == "boolean"
