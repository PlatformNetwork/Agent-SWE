"""Unit tests for orchestrator models."""

import pytest
from datetime import datetime, timezone, timedelta

from swe_forge.orchestrator.models import (
    TaskState,
    TestFile,
    GenerateTestsResult,
    ValidateTestsResult,
    BuildDockerResult,
    VerifyResult,
    RepairResult,
    ScoreResult,
    PublishResult,
    OrchestratorTask,
    OrchestratorStats,
)


class TestTaskState:
    """Tests for TaskState enum."""

    def test_task_state_values(self):
        """Test that TaskState has expected values."""
        assert TaskState.PENDING == "pending"
        assert TaskState.GENERATING_TESTS == "generating_tests"
        assert TaskState.VALIDATING_TESTS == "validating_tests"
        assert TaskState.BUILDING_DOCKER == "building_docker"
        assert TaskState.VERIFYING == "verifying"
        assert TaskState.REPAIRING == "repairing"
        assert TaskState.SCORING == "scoring"
        assert TaskState.PUBLISHING == "publishing"
        assert TaskState.COMPLETED == "completed"
        assert TaskState.REJECTED == "rejected"
        assert TaskState.FAILED == "failed"

    def test_task_state_is_str_enum(self):
        """Test that TaskState is a str enum."""
        assert isinstance(TaskState.PENDING, str)
        assert TaskState.PENDING.value == "pending"


class TestResultDataclasses:
    """Tests for result dataclasses."""

    def test_test_file(self):
        """Test TestFile dataclass."""
        tf = TestFile(path="tests/test_example.py", content="def test_x(): pass")
        assert tf.path == "tests/test_example.py"
        assert tf.content == "def test_x(): pass"

    def test_generate_tests_result_success(self):
        """Test GenerateTestsResult with successful generation."""
        result = GenerateTestsResult(
            success=True,
            tests={"fail_to_pass": ["pytest test.py"], "pass_to_pass": []},
            test_files=[TestFile(path="test.py", content="pass")],
            install_commands=["pip install -e ."],
            turn_count=5,
        )
        assert result.success is True
        assert result.error is None
        assert len(result.test_files) == 1
        assert result.turn_count == 5

    def test_generate_tests_result_failure(self):
        """Test GenerateTestsResult with failed generation."""
        result = GenerateTestsResult(
            success=False,
            error="API key not set",
        )
        assert result.success is False
        assert result.error == "API key not set"
        assert result.test_files == []

    def test_validate_tests_result(self):
        """Test ValidateTestsResult dataclass."""
        result = ValidateTestsResult(
            success=True,
            has_assertions=True,
            has_valid_syntax=True,
            relevant_to_patch=True,
        )
        assert result.success is True
        assert result.issues == []

    def test_validate_tests_result_with_issues(self):
        """Test ValidateTestsResult with issues."""
        result = ValidateTestsResult(
            success=False,
            has_assertions=False,
            has_valid_syntax=True,
            relevant_to_patch=False,
            issues=["No assertions found"],
            error="No assertions found",
        )
        assert result.success is False
        assert "No assertions found" in result.issues

    def test_build_docker_result_success(self):
        """Test BuildDockerResult with successful build."""
        result = BuildDockerResult(
            success=True,
            image_name="myimage:latest",
            build_time_seconds=45.5,
        )
        assert result.success is True
        assert result.image_name == "myimage:latest"
        assert result.build_time_seconds == 45.5

    def test_verify_result(self):
        """Test VerifyResult dataclass."""
        result = VerifyResult(
            success=True,
            before_patch_failed=True,
            after_patch_passed=True,
            needs_repair=False,
        )
        assert result.success is True
        assert result.before_patch_failed is True
        assert result.after_patch_passed is True

    def test_repair_result(self):
        """Test RepairResult dataclass."""
        result = RepairResult(
            success=True,
            attempts=3,
            fix_applied="Fixed import statement",
        )
        assert result.success is True
        assert result.attempts == 3
        assert result.fix_applied == "Fixed import statement"

    def test_score_result(self):
        """Test ScoreResult dataclass."""
        result = ScoreResult(
            score=0.85,
            complexity_score=0.9,
            test_quality_score=0.8,
            verification_score=0.85,
        )
        assert result.score == 0.85
        assert result.complexity_score == 0.9

    def test_publish_result(self):
        """Test PublishResult dataclass."""
        result = PublishResult(
            success=True,
            dataset_name="CortexLM/swe-forge",
            task_id="owner-repo-123",
        )
        assert result.success is True
        assert result.dataset_name == "CortexLM/swe-forge"


class TestOrchestratorTask:
    """Tests for OrchestratorTask dataclass."""

    def test_create_task(self):
        """Test creating a new OrchestratorTask."""
        task = OrchestratorTask(
            task_id="test-123",
            repo_url="https://github.com/owner/repo",
            base_commit="abc123",
            patch="diff --git a/file.py",
        )
        assert task.task_id == "test-123"
        assert task.state == TaskState.PENDING
        assert task.language == "unknown"

    def test_transition_to(self):
        """Test state transition."""
        task = OrchestratorTask(task_id="test-123")
        original_updated = task.updated_at

        task.transition_to(TaskState.GENERATING_TESTS)

        assert task.state == TaskState.GENERATING_TESTS
        assert task.updated_at >= original_updated

    def test_is_terminal_completed(self):
        """Test is_terminal returns True for COMPLETED."""
        task = OrchestratorTask(task_id="test-123", state=TaskState.COMPLETED)
        assert task.is_terminal() is True

    def test_is_terminal_rejected(self):
        """Test is_terminal returns True for REJECTED."""
        task = OrchestratorTask(task_id="test-123", state=TaskState.REJECTED)
        assert task.is_terminal() is True

    def test_is_terminal_failed(self):
        """Test is_terminal returns True for FAILED."""
        task = OrchestratorTask(task_id="test-123", state=TaskState.FAILED)
        assert task.is_terminal() is True

    def test_is_terminal_not_terminal(self):
        """Test is_terminal returns False for non-terminal states."""
        task = OrchestratorTask(task_id="test-123", state=TaskState.PENDING)
        assert task.is_terminal() is False

        task.transition_to(TaskState.GENERATING_TESTS)
        assert task.is_terminal() is False


class TestOrchestratorStats:
    """Tests for OrchestratorStats dataclass."""

    def test_empty_stats(self):
        """Test empty stats have zero rates."""
        stats = OrchestratorStats()
        assert stats.pass_rate() == 0.0
        assert stats.failure_rate() == 0.0
        assert stats.average_time_per_task() == 0.0

    def test_pass_rate(self):
        """Test pass_rate calculation."""
        stats = OrchestratorStats(
            total_tasks=10,
            state_counts={
                TaskState.COMPLETED: 7,
                TaskState.FAILED: 2,
                TaskState.REJECTED: 1,
            },
        )
        assert stats.pass_rate() == 0.7

    def test_pass_rate_zero_tasks(self):
        """Test pass_rate returns 0.0 for zero tasks."""
        stats = OrchestratorStats(total_tasks=0)
        assert stats.pass_rate() == 0.0

    def test_failure_rate(self):
        """Test failure_rate calculation."""
        stats = OrchestratorStats(
            total_tasks=10,
            state_counts={
                TaskState.COMPLETED: 7,
                TaskState.FAILED: 2,
                TaskState.REJECTED: 1,
            },
        )
        # Failed + Rejected = 2 + 1 = 3, 3/10 = 0.3
        assert stats.failure_rate() == 0.3

    def test_failure_rate_zero_tasks(self):
        """Test failure_rate returns 0.0 for zero tasks."""
        stats = OrchestratorStats(total_tasks=0)
        assert stats.failure_rate() == 0.0

    def test_average_time_per_task(self):
        """Test average_time_per_task calculation."""
        stats = OrchestratorStats(
            total_tasks=5,
            timing={
                "generate": 100.0,
                "validate": 50.0,
                "build": 200.0,
            },
        )
        # total time = 350, tasks = 5, avg = 70
        assert stats.average_time_per_task() == 70.0

    def test_average_time_no_tasks(self):
        """Test average_time_per_task with no tasks."""
        stats = OrchestratorStats(total_tasks=0, timing={"generate": 100.0})
        assert stats.average_time_per_task() == 0.0
