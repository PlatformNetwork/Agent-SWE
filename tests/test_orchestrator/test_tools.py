"""Unit tests for orchestrator tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from swe_forge.orchestrator.models import (
    ValidateTestsResult,
    VerifyResult,
    ScoreResult,
)
from swe_forge.orchestrator.tools import (
    validate_tests,
    score_task,
    reject_task,
    generate_tests,
    build_docker,
    verify_fail_to_pass,
    repair_test,
    publish_task,
)


class TestValidateTests:
    """Tests for validate_tests function."""

    @pytest.mark.asyncio
    async def test_validate_tests_with_valid_python(self):
        """Test validation of valid Python test with assertions."""
        tests = [
            {
                "path": "tests/test_example.py",
                "content": "def test_add():\n    assert 1 + 1 == 2",
            }
        ]
        patch = "--- a/src/module.py\n+++ b/src/module.py\n@@ -1,1 +1,2 @@"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_valid_syntax is True
        assert result.has_assertions is True

    @pytest.mark.asyncio
    async def test_validate_tests_syntax_error(self):
        """Test validation catches syntax errors."""
        tests = [
            {
                "path": "tests/test_bad.py",
                "content": "def test_x(:\n    pass",  # Invalid syntax
            }
        ]
        patch = "--- a/src/module.py"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_valid_syntax is False
        assert len(result.issues) > 0
        assert "Syntax error" in result.issues[0]

    @pytest.mark.asyncio
    async def test_validate_tests_missing_assertions(self):
        """Test validation catches missing assertions."""
        tests = [
            {
                "path": "tests/test_no_assert.py",
                "content": "def test_x():\n    x = 1",  # No assertions
            }
        ]
        patch = "--- a/src/module.py"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_assertions is False
        assert any("No assertions" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_tests_empty_content(self):
        """Test validation handles empty test content."""
        tests = [{"path": "tests/test_empty.py", "content": ""}]
        patch = "--- a/src/module.py"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_assertions is False

    @pytest.mark.asyncio
    async def test_validate_tests_jest_patterns(self):
        """Test validation recognizes Jest assertion patterns."""
        tests = [
            {
                "path": "tests/test.ts",
                "content": "test('adds', () => {\n  expect(1 + 1).toBe(2);\n});",
            }
        ]
        patch = "--- a/src/module.ts"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_assertions is True

    @pytest.mark.asyncio
    async def test_validate_tests_pytest_assert(self):
        """Test validation recognizes pytest assertions."""
        tests = [
            {
                "path": "tests/test_pytest.py",
                "content": "def test_x():\n    assert True",
            }
        ]
        patch = "--- a/src/module.py"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_assertions is True

    @pytest.mark.asyncio
    async def test_validate_tests_unittest_assert(self):
        """Test validation recognizes unittest assertions."""
        tests = [
            {
                "path": "tests/test_unittest.py",
                "content": "class TestX:\n    def test_x(self):\n        self.assertTrue(True)",
            }
        ]
        patch = "--- a/src/module.py"

        result = await validate_tests("task-1", tests, patch)

        assert result.has_assertions is True


class TestScoreTask:
    """Tests for score_task function."""

    @pytest.mark.asyncio
    async def test_score_task_full_success(self):
        """Test scoring with fully successful results."""
        validation = ValidateTestsResult(
            success=True,
            has_assertions=True,
            has_valid_syntax=True,
        )
        verify_result = VerifyResult(
            success=True,
            before_patch_failed=True,
            after_patch_passed=True,
        )

        with patch(
            "swe_forge.evaluators.complexity_evaluator.ComplexityEvaluator"
        ) as mock_eval:
            mock_eval.return_value.evaluate.return_value = MagicMock(score=0.8)

            result = await score_task(
                "task-1",
                validation,
                verify_result,
                patch="diff content",
                tests=["pytest test.py"],
            )

        assert isinstance(result, ScoreResult)
        assert 0.0 <= result.score <= 1.0
        assert result.verification_score == 1.0
        assert result.test_quality_score == 1.0

    @pytest.mark.asyncio
    async def test_score_task_partial_validation(self):
        """Test scoring with partial validation success."""
        validation = ValidateTestsResult(
            success=False,
            has_assertions=True,
            has_valid_syntax=True,
        )
        verify_result = VerifyResult(
            success=True,
            before_patch_failed=True,
            after_patch_passed=True,
        )

        with patch(
            "swe_forge.evaluators.complexity_evaluator.ComplexityEvaluator"
        ) as mock_eval:
            mock_eval.return_value.evaluate.return_value = MagicMock(score=0.5)

            result = await score_task("task-1", validation, verify_result)

        assert result.test_quality_score == 0.7

    @pytest.mark.asyncio
    async def test_score_task_failed_verification(self):
        """Test scoring with failed verification."""
        validation = ValidateTestsResult(success=True)
        verify_result = VerifyResult(
            success=False,
            before_patch_failed=True,
            after_patch_passed=False,
        )

        with patch(
            "swe_forge.evaluators.complexity_evaluator.ComplexityEvaluator"
        ) as mock_eval:
            mock_eval.return_value.evaluate.return_value = MagicMock(score=0.5)

            result = await score_task("task-1", validation, verify_result)

        assert result.verification_score == 0.3

    @pytest.mark.asyncio
    async def test_score_task_complexity_evaluator_failure(self):
        """Test scoring handles complexity evaluator failure."""
        validation = ValidateTestsResult(success=True)
        verify_result = VerifyResult(success=True)

        with patch(
            "swe_forge.evaluators.complexity_evaluator.ComplexityEvaluator"
        ) as mock_eval:
            mock_eval.return_value.evaluate.side_effect = Exception("Eval failed")

            result = await score_task("task-1", validation, verify_result)

        assert result.complexity_score == 0.5


class TestRejectTask:
    """Tests for reject_task function."""

    @pytest.mark.asyncio
    async def test_reject_task_logs_reason(self, caplog):
        """Test that reject_task logs the rejection reason."""
        with caplog.at_level(logging.INFO):
            await reject_task("task-123", "complexity_too_low")

        assert "task-123" in caplog.text
        assert "REJECTED" in caplog.text
        assert "complexity_too_low" in caplog.text

    @pytest.mark.asyncio
    async def test_reject_task_with_details(self, caplog):
        """Test reject_task logs with details."""
        with caplog.at_level(logging.INFO):
            await reject_task(
                "task-123",
                "validation_failed",
                details={"score": 0.2, "threshold": 0.5},
            )

        assert "task-123" in caplog.text
        assert "validation_failed" in caplog.text
        assert "score" in caplog.text


class TestGenerateTests:
    """Tests for generate_tests function."""

    @pytest.mark.asyncio
    async def test_generate_tests_no_api_key(self):
        """Test generate_tests fails without API key."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=False):
            result = await generate_tests(
                "task-1",
                "patch",
                "https://github.com/owner/repo",
                "abc123",
                "python",
            )

        assert result.success is False
        assert "OPENROUTER_API_KEY" in result.error


class TestPublishTask:
    """Tests for publish_task function."""

    @pytest.mark.asyncio
    async def test_publish_task_below_threshold(self):
        """Test publish_task rejects low scores."""
        result = await publish_task("task-1", 0.3, min_score=0.5)

        assert result.success is False
        assert "below threshold" in result.error

    @pytest.mark.asyncio
    async def test_publish_task_no_hf_token(self):
        """Test publish_task fails without HF token."""
        with patch.dict("os.environ", {"HF_TOKEN": ""}, clear=False):
            result = await publish_task("task-1", 0.8, min_score=0.5)

        assert result.success is False
        assert "HF_TOKEN not set" in result.error

    @pytest.mark.asyncio
    async def test_publish_task_success(self):
        """Test publish_task with valid token."""
        with patch.dict("os.environ", {"HF_TOKEN": "test_token"}, clear=False):
            with patch("huggingface_hub.HfApi") as mock_api:
                mock_api.return_value.whoami.return_value = {"name": "test_user"}

                result = await publish_task(
                    "task-1",
                    0.8,
                    min_score=0.5,
                    dataset_name="test/dataset",
                )

        assert result.success is True
        assert result.dataset_name == "test/dataset"


class TestBuildDocker:
    """Tests for build_docker function."""

    @pytest.mark.asyncio
    async def test_build_docker_creates_temp_files(self):
        """Test build_docker creates proper temp structure."""
        tests = [{"path": "test.py", "content": "def test_x(): pass"}]

        with patch(
            "swe_forge.publish.docker_builder.build_docker_image",
            new_callable=AsyncMock,
        ) as mock_build:
            mock_build.return_value = MagicMock(
                success=True, image_name="test:image", error=None
            )

            result = await build_docker(
                "task-1",
                tests,
                "https://github.com/owner/repo",
                "abc123",
                "python",
            )

        assert result.success is True


class TestVerifyFailToPass:
    """Tests for verify_fail_to_pass function."""

    @pytest.mark.asyncio
    async def test_verify_fail_to_pass(self):
        """Test verify_fail_to_pass delegates to verify_docker_image."""
        with patch(
            "swe_forge.publish.docker_builder.verify_docker_image",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = MagicMock(
                success=True,
                before_patch_fail=True,
                after_patch_pass=True,
                error=None,
            )

            result = await verify_fail_to_pass(
                "task-1",
                "image:latest",
                ["pytest test.py"],
                "patch content",
            )

        assert result.success is True
        assert result.before_patch_failed is True
        assert result.after_patch_passed is True


class TestRepairTest:
    """Tests for repair_test function."""

    @pytest.mark.asyncio
    async def test_repair_test_no_api_key(self):
        """Test repair_test fails without API key."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=False):
            result = await repair_test("task-1", "error output")

        assert result.success is False
        assert "OPENROUTER_API_KEY" in result.error
