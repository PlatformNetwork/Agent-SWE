"""Tests for test repair agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from swe_forge.agents import Diagnosis, Fix, RepairAttempt, TestRepairAgent
from swe_forge.llm import GenerationRequest, GenerationResponse, Choice, Message, Usage


class TestDiagnosis:
    def test_diagnosis_defaults(self):
        diagnosis = Diagnosis(fixable=True, reason="Test error")
        assert diagnosis.fixable is True
        assert diagnosis.reason == "Test error"
        assert diagnosis.suggested_fix is None
        assert diagnosis.error_type is None
        assert diagnosis.confidence == 0.0

    def test_diagnosis_full(self):
        diagnosis = Diagnosis(
            fixable=True,
            reason="Missing dependency",
            suggested_fix="pip install pytest",
            error_type="dependency",
            confidence=0.8,
        )
        assert diagnosis.fixable is True
        assert diagnosis.reason == "Missing dependency"
        assert diagnosis.suggested_fix == "pip install pytest"
        assert diagnosis.error_type == "dependency"
        assert diagnosis.confidence == 0.8


class TestFix:
    def test_fix_defaults(self):
        fix = Fix(description="Test fix")
        assert fix.description == "Test fix"
        assert fix.modified_test is None
        assert fix.skip_task is False
        assert fix.patch_modification is None
        assert fix.install_commands == []

    def test_fix_full(self):
        fix = Fix(
            description="Add dependency",
            modified_test="new test content",
            skip_task=False,
            patch_modification="patch content",
            install_commands=["pip install pytest", "pip install requests"],
        )
        assert fix.description == "Add dependency"
        assert fix.modified_test == "new test content"
        assert fix.skip_task is False
        assert fix.patch_modification == "patch content"
        assert fix.install_commands == ["pip install pytest", "pip install requests"]


class TestRepairAttempt:
    def test_repair_attempt_defaults(self):
        diagnosis = Diagnosis(fixable=True, reason="Test")
        attempt = RepairAttempt(attempt_number=1, diagnosis=diagnosis)
        assert attempt.attempt_number == 1
        assert attempt.diagnosis == diagnosis
        assert attempt.fix_applied is None
        assert attempt.success is False
        assert attempt.error is None

    def test_repair_attempt_with_fix(self):
        diagnosis = Diagnosis(fixable=True, reason="Test")
        fix = Fix(description="Fix applied")
        attempt = RepairAttempt(
            attempt_number=2,
            diagnosis=diagnosis,
            fix_applied=fix,
            success=True,
        )
        assert attempt.attempt_number == 2
        assert attempt.fix_applied == fix
        assert attempt.success is True


class TestTestRepairAgent:
    def test_init(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        assert agent.llm_client == mock_client
        assert agent.model == "openai/gpt-4o-mini"

    def test_init_custom_model(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client, model="custom/model")
        assert agent.model == "custom/model"

    def test_parse_json_response_valid(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        result = agent._parse_json_response('{"fixable": true, "reason": "test"}')
        assert result == {"fixable": True, "reason": "test"}

    def test_parse_json_response_with_markdown(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        result = agent._parse_json_response(
            '```json\n{"fixable": false, "reason": "wrapped"}\n```'
        )
        assert result == {"fixable": False, "reason": "wrapped"}

    def test_parse_json_response_empty(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        result = agent._parse_json_response(None)
        assert result == {}

    def test_parse_json_response_invalid(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        result = agent._parse_json_response("not json at all")
        assert result == {}

    @pytest.mark.asyncio
    async def test_diagnose_failure_success(self):
        mock_client = AsyncMock()
        response = GenerationResponse(
            id="test-id",
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=Message.assistant(
                        '{"fixable": true, "reason": "Missing dep", "suggested_fix": "pip install x", "error_type": "dependency", "confidence": 0.9}'
                    ),
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )
        mock_client.complete.return_value = response

        agent = TestRepairAgent(mock_client)
        diagnosis = await agent.diagnose_failure(
            test_output={"exit_code": 1},
            patch="patch content",
            repo_url="https://github.com/test/repo",
            error="Test failed",
        )

        assert diagnosis.fixable is True
        assert diagnosis.reason == "Missing dep"
        assert diagnosis.suggested_fix == "pip install x"
        assert diagnosis.error_type == "dependency"
        assert diagnosis.confidence == 0.9

    @pytest.mark.asyncio
    async def test_diagnose_failure_no_response(self):
        mock_client = AsyncMock()
        response = GenerationResponse(
            id="test-id",
            model="test-model",
            choices=[
                Choice(index=0, message=Message.assistant(""), finish_reason="stop")
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )
        mock_client.complete.return_value = response

        agent = TestRepairAgent(mock_client)
        diagnosis = await agent.diagnose_failure(
            test_output={},
            patch="",
            repo_url="",
            error="error",
        )

        assert diagnosis.fixable is False
        assert "No response" in diagnosis.reason

    @pytest.mark.asyncio
    async def test_generate_fix_unfixable(self):
        mock_client = MagicMock()
        agent = TestRepairAgent(mock_client)
        diagnosis = Diagnosis(fixable=False, reason="Cannot fix")
        fix = await agent.generate_fix(diagnosis)

        assert fix.skip_task is True
        assert "unfixable" in fix.description.lower()

    @pytest.mark.asyncio
    async def test_generate_fix_success(self):
        mock_client = AsyncMock()
        response = GenerationResponse(
            id="test-id",
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=Message.assistant(
                        '{"description": "Install dep", "install_commands": ["pip install x"], "skip_task": false}'
                    ),
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )
        mock_client.complete.return_value = response

        agent = TestRepairAgent(mock_client)
        diagnosis = Diagnosis(
            fixable=True, reason="Missing dep", suggested_fix="Install the dependency"
        )
        fix = await agent.generate_fix(diagnosis)

        assert fix.description == "Install dep"
        assert fix.install_commands == ["pip install x"]
        assert fix.skip_task is False
