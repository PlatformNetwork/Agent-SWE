"""Test verification module for running and verifying SWE-bench tests.

This module provides functionality to run fail_to_pass and pass_to_pass tests
in a sandbox environment and capture results with timing information.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from swe_forge.swe.models import SweTask

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Sandbox Protocol
# ---------------------------------------------------------------------------


class SandboxProtocol(Protocol):
    """Protocol for sandbox implementations used by verify_tests."""

    async def run_command(
        self, cmd: str, *, timeout: float | None = None
    ) -> "ExecResultProtocol":
        """Execute a command in the sandbox."""
        ...

    @property
    def container_id(self) -> str | None:
        """Get container ID."""
        ...

    @property
    def workspace_dir(self) -> str:
        """Get workspace directory."""
        ...


class ExecResultProtocol(Protocol):
    """Protocol for command execution results."""

    @property
    def exit_code(self) -> int: ...

    @property
    def stdout(self) -> str: ...

    @property
    def stderr(self) -> str: ...


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------


@dataclass
class TestVerificationResult:
    """Result of test verification for a SWE task.

    Attributes:
        fail_to_pass_results: List of (command, passed, duration_seconds, error_message).
            Each tuple represents a test command from fail_to_pass tests.
        pass_to_pass_results: List of (command, passed, duration_seconds, error_message).
            Each tuple represents a test command from pass_to_pass tests (regression checks).
        total_duration: Total time taken for all test executions in seconds.
        all_passed: True if all tests (both fail_to_pass and pass_to_pass) passed.
    """

    fail_to_pass_results: list[tuple[str, bool, float, str | None]] = field(
        default_factory=list
    )
    pass_to_pass_results: list[tuple[str, bool, float, str | None]] = field(
        default_factory=list
    )
    total_duration: float = 0.0
    all_passed: bool = True

    @property
    def fail_to_pass_passed_count(self) -> int:
        """Count of fail_to_pass tests that passed."""
        return sum(1 for _, passed, _, _ in self.fail_to_pass_results if passed)

    @property
    def pass_to_pass_passed_count(self) -> int:
        """Count of pass_to_pass tests that passed."""
        return sum(1 for _, passed, _, _ in self.pass_to_pass_results if passed)

    @property
    def fail_to_pass_total_count(self) -> int:
        """Total count of fail_to_pass tests."""
        return len(self.fail_to_pass_results)

    @property
    def pass_to_pass_total_count(self) -> int:
        """Total count of pass_to_pass tests."""
        return len(self.pass_to_pass_results)

    @property
    def summary(self) -> str:
        """Human-readable summary of test verification results."""
        f2p_passed = self.fail_to_pass_passed_count
        f2p_total = self.fail_to_pass_total_count
        p2p_passed = self.pass_to_pass_passed_count
        p2p_total = self.pass_to_pass_total_count
        status = "PASSED" if self.all_passed else "FAILED"

        return (
            f"Test verification {status} "
            f"(fail_to_pass: {f2p_passed}/{f2p_total}, "
            f"pass_to_pass: {p2p_passed}/{p2p_total}, "
            f"duration: {self.total_duration:.2f}s)"
        )


# ---------------------------------------------------------------------------
# Test Verification Function
# ---------------------------------------------------------------------------


async def verify_tests(
    sandbox: SandboxProtocol,
    task: "SweTask",
    timeout_per_test: float = 60.0,
) -> TestVerificationResult:
    """Run and verify tests for a SWE task.

    This function executes fail_to_pass tests (which should pass after a fix)
    and pass_to_pass tests (regression checks that should still pass).

    Args:
        sandbox: Sandbox with repository at the commit to be verified.
        task: The SWE task containing test commands.
        timeout_per_test: Timeout in seconds for each test command (default: 60.0).

    Returns:
        TestVerificationResult with pass/fail status and timing for each test.

    Example:
        result = await verify_tests(sandbox, task, timeout_per_test=120.0)
        if result.all_passed:
            print("All tests passed!")
        else:
            print(f"Tests failed: {result.summary}")
    """
    start_time = time.monotonic()

    result = TestVerificationResult()

    # Run fail_to_pass tests
    for cmd in task.fail_to_pass:
        test_result = await _run_single_test(sandbox, cmd, timeout_per_test)
        result.fail_to_pass_results.append(test_result)
        if not test_result[1]:  # passed is False
            result.all_passed = False

    # Run pass_to_pass tests (regression check)
    for cmd in task.pass_to_pass:
        test_result = await _run_single_test(sandbox, cmd, timeout_per_test)
        result.pass_to_pass_results.append(test_result)
        if not test_result[1]:  # passed is False
            result.all_passed = False

    result.total_duration = time.monotonic() - start_time

    logger.info(result.summary)

    return result


async def _run_single_test(
    sandbox: "SandboxProtocol",
    cmd: str,
    timeout: float,
) -> tuple[str, bool, float, str | None]:
    """Run a single test command and capture results.

    Args:
        sandbox: Sandbox to run the test in.
        cmd: Test command to execute.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (command, passed, duration_seconds, error_message).
    """
    start = time.monotonic()
    error_message: str | None = None

    try:
        exec_result = await sandbox.run_command(cmd, timeout=timeout)
        duration = time.monotonic() - start
        passed = exec_result.exit_code == 0

        if not passed:
            # Capture error from stderr or stdout
            error_message = exec_result.stderr or exec_result.stdout
            if error_message:
                # Truncate long error messages
                error_message = _truncate(error_message, 500)

        logger.debug(
            f"Test '{cmd}': {'PASS' if passed else 'FAIL'} (duration: {duration:.2f}s)"
        )

        return (cmd, passed, duration, error_message)

    except TimeoutError:
        duration = time.monotonic() - start
        error_message = f"Test timed out after {timeout}s"
        logger.warning(f"Test '{cmd}': {error_message}")
        return (cmd, False, duration, error_message)

    except Exception as e:
        duration = time.monotonic() - start
        error_message = f"Test execution error: {e}"
        logger.exception(f"Test '{cmd}' failed with exception")
        return (cmd, False, duration, error_message)


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max length with ellipsis.

    Args:
        s: String to truncate.
        max_len: Maximum length.

    Returns:
        Truncated string with '...' suffix if needed.
    """
    if len(s) <= max_len:
        return s

    # Find a safe boundary for truncation
    end = max_len
    while end > 0 and not s[end - 1].isprintable():
        end -= 1

    return s[:end] + "..."
