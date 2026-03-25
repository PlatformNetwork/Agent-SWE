"""Tests for swe_forge.swe.test_verification module."""

import pytest
from dataclasses import dataclass

from swe_forge.swe.test_verification import (
    TestVerificationResult,
    verify_tests,
    _truncate,
)
from swe_forge.swe.models import SweTask


@dataclass
class MockExecResult:
    stdout: str
    stderr: str
    exit_code: int


class MockSandbox:
    def __init__(self, results: list[MockExecResult] | None = None):
        self.results = results or []
        self.call_count = 0
        self.commands: list[tuple[str, float | None]] = []
        self._container_id = "test-container-123"
        self._workspace_dir = "/repo"

    async def run_command(self, cmd: str, *, timeout: float | None = None):
        self.commands.append((cmd, timeout))
        if self.call_count < len(self.results):
            result = self.results[self.call_count]
            self.call_count += 1
            return result
        return MockExecResult(stdout="", stderr="", exit_code=0)

    @property
    def container_id(self):
        return self._container_id

    @property
    def workspace_dir(self):
        return self._workspace_dir


def create_task(
    *,
    task_id: str = "test-task-1",
    fail_to_pass: list[str] | None = None,
    pass_to_pass: list[str] | None = None,
) -> SweTask:
    return SweTask(
        id=task_id,
        repo="owner/repo",
        base_commit="abc123def456",
        merge_commit="def456",
        language="python",
        fail_to_pass=fail_to_pass or [],
        pass_to_pass=pass_to_pass or [],
        prompt="Fix the bug",
    )


class TestTestVerificationResult:
    def test_result_creation(self):
        result = TestVerificationResult(
            fail_to_pass_results=[("pytest test.py", True, 1.5, None)],
            pass_to_pass_results=[("pytest other.py", True, 0.5, None)],
            total_duration=2.0,
            all_passed=True,
        )
        assert result.fail_to_pass_total_count == 1
        assert result.pass_to_pass_total_count == 1
        assert result.all_passed is True

    def test_result_defaults(self):
        result = TestVerificationResult()
        assert result.fail_to_pass_results == []
        assert result.pass_to_pass_results == []
        assert result.total_duration == 0.0
        assert result.all_passed is True

    def test_passed_counts(self):
        result = TestVerificationResult(
            fail_to_pass_results=[
                ("pytest a.py", True, 1.0, None),
                ("pytest b.py", False, 1.0, "Error"),
                ("pytest c.py", True, 1.0, None),
            ],
            pass_to_pass_results=[
                ("pytest d.py", True, 1.0, None),
                ("pytest e.py", True, 1.0, None),
            ],
            all_passed=False,
        )
        assert result.fail_to_pass_passed_count == 2
        assert result.pass_to_pass_passed_count == 2
        assert result.fail_to_pass_total_count == 3
        assert result.pass_to_pass_total_count == 2

    def test_summary_all_passed(self):
        result = TestVerificationResult(
            fail_to_pass_results=[("pytest test.py", True, 1.0, None)],
            pass_to_pass_results=[("pytest other.py", True, 1.0, None)],
            total_duration=2.0,
            all_passed=True,
        )
        assert "PASSED" in result.summary
        assert "1/1" in result.summary

    def test_summary_some_failed(self):
        result = TestVerificationResult(
            fail_to_pass_results=[("pytest test.py", False, 1.0, "Error")],
            pass_to_pass_results=[("pytest other.py", True, 1.0, None)],
            total_duration=2.0,
            all_passed=False,
        )
        assert "FAILED" in result.summary
        assert "0/1" in result.summary


class TestVerifyTests:
    @pytest.mark.asyncio
    async def test_all_tests_pass(self):
        task = create_task(
            fail_to_pass=["pytest test_bug.py"],
            pass_to_pass=["pytest test_existing.py"],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="OK", stderr="", exit_code=0),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.all_passed is True
        assert result.fail_to_pass_passed_count == 1
        assert result.pass_to_pass_passed_count == 1

    @pytest.mark.asyncio
    async def test_fail_to_pass_fails(self):
        task = create_task(
            fail_to_pass=["pytest test_bug.py"],
            pass_to_pass=[],
        )

        results = [
            MockExecResult(stdout="", stderr="FAILED", exit_code=1),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.all_passed is False
        assert result.fail_to_pass_passed_count == 0
        assert result.fail_to_pass_results[0][2] > 0

    @pytest.mark.asyncio
    async def test_pass_to_pass_fails_regression(self):
        task = create_task(
            fail_to_pass=["pytest test_bug.py"],
            pass_to_pass=["pytest test_existing.py"],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="", stderr="REGRESSION", exit_code=1),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.all_passed is False
        assert result.fail_to_pass_passed_count == 1
        assert result.pass_to_pass_passed_count == 0

    @pytest.mark.asyncio
    async def test_empty_test_lists(self):
        task = create_task(
            fail_to_pass=[],
            pass_to_pass=[],
        )

        sandbox = MockSandbox(results=[])

        result = await verify_tests(sandbox, task)

        assert result.all_passed is True
        assert result.fail_to_pass_total_count == 0
        assert result.pass_to_pass_total_count == 0

    @pytest.mark.asyncio
    async def test_multiple_tests_mixed_results(self):
        task = create_task(
            fail_to_pass=["pytest a.py", "pytest b.py"],
            pass_to_pass=["pytest c.py", "pytest d.py"],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="", stderr="FAIL", exit_code=1),
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="", stderr="FAIL", exit_code=1),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.all_passed is False
        assert result.fail_to_pass_passed_count == 1
        assert result.pass_to_pass_passed_count == 1

    @pytest.mark.asyncio
    async def test_error_message_captured(self):
        task = create_task(
            fail_to_pass=["pytest test.py"],
            pass_to_pass=[],
        )

        results = [
            MockExecResult(stdout="", stderr="AssertionError: x != y", exit_code=1),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.fail_to_pass_results[0][3] == "AssertionError: x != y"

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        task = create_task(
            fail_to_pass=["pytest slow_test.py"],
            pass_to_pass=[],
        )

        class TimeoutSandbox(MockSandbox):
            async def run_command(self, cmd: str, *, timeout: float | None = None):
                self.commands.append((cmd, timeout))
                raise TimeoutError("Test timed out")

        sandbox = TimeoutSandbox()

        result = await verify_tests(sandbox, task, timeout_per_test=5.0)

        assert result.all_passed is False
        assert result.fail_to_pass_results[0][3] is not None
        assert "timed out" in result.fail_to_pass_results[0][3]

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        task = create_task(
            fail_to_pass=["pytest test.py"],
            pass_to_pass=[],
        )

        class ExceptionSandbox(MockSandbox):
            async def run_command(self, cmd: str, *, timeout: float | None = None):
                self.commands.append((cmd, timeout))
                raise RuntimeError("Sandbox crashed")

        sandbox = ExceptionSandbox()

        result = await verify_tests(sandbox, task)

        assert result.all_passed is False
        assert result.fail_to_pass_results[0][3] is not None
        assert "Sandbox crashed" in result.fail_to_pass_results[0][3]

    @pytest.mark.asyncio
    async def test_timing_captured(self):
        task = create_task(
            fail_to_pass=["pytest test.py"],
            pass_to_pass=["pytest other.py"],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="OK", stderr="", exit_code=0),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.total_duration > 0
        assert result.fail_to_pass_results[0][2] >= 0
        assert result.pass_to_pass_results[0][2] >= 0

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        task = create_task(
            fail_to_pass=["pytest test.py"],
            pass_to_pass=[],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
        ]
        sandbox = MockSandbox(results=results)

        await verify_tests(sandbox, task, timeout_per_test=120.0)

        assert sandbox.commands[0][1] == 120.0


class TestTruncate:
    def test_short_string(self):
        s = "hello"
        result = _truncate(s, 10)
        assert result == "hello"

    def test_exact_length(self):
        s = "hello"
        result = _truncate(s, 5)
        assert result == "hello"

    def test_long_string(self):
        s = "a" * 100
        result = _truncate(s, 50)
        assert len(result) == 53
        assert result.endswith("...")

    def test_empty_string(self):
        result = _truncate("", 10)
        assert result == ""

    def test_unicode_string(self):
        s = "hello world"
        result = _truncate(s, 5)
        assert result == "hello..."

    def test_non_printable_boundary(self):
        s = "hello\x00world"
        result = _truncate(s, 10)
        assert len(result) <= 15


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_verification_workflow(self):
        task = create_task(
            task_id="integration-test-1",
            fail_to_pass=["pytest tests/test_fix.py", "pytest tests/test_feature.py"],
            pass_to_pass=["pytest tests/test_regression.py"],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
            MockExecResult(stdout="", stderr="1 failed", exit_code=1),
            MockExecResult(stdout="OK", stderr="", exit_code=0),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert result.all_passed is False
        assert result.fail_to_pass_passed_count == 1
        assert result.pass_to_pass_passed_count == 1
        assert "FAILED" in result.summary
        assert "integration-test-1" in result.summary or "1/2" in result.summary

    @pytest.mark.asyncio
    async def test_verification_result_serializable(self):
        task = create_task(
            fail_to_pass=["pytest test.py"],
            pass_to_pass=[],
        )

        results = [
            MockExecResult(stdout="OK", stderr="", exit_code=0),
        ]
        sandbox = MockSandbox(results=results)

        result = await verify_tests(sandbox, task)

        assert isinstance(result.fail_to_pass_results, list)
        assert isinstance(result.pass_to_pass_results, list)
        assert isinstance(result.total_duration, float)
        assert isinstance(result.all_passed, bool)
