"""Dual-commit validation for SWE tasks.

This module provides the dual-commit validation pattern that verifies:
1. fail_to_pass tests FAIL on base commit (before patch)
2. fail_to_pass tests PASS after patch is applied
3. pass_to_pass tests PASS after patch is applied

The dual-commit pattern ensures test commands correctly validate
the bug-fix behavior without false positives or regressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from swe_forge.swe.models import SweTask

logger = getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DualCommitResult:
    """Result of dual-commit validation.

    Attributes:
        passed: Whether all validation checks passed.
        reasons: List of failure reasons if validation failed.
        fail_to_pass_before: Results of fail_to_pass tests on base commit.
            Each tuple is (command, failed_as_expected) where failed_as_expected
            is True if the test failed (as it should on base).
        fail_to_pass_after: Results of fail_to_pass tests after patch.
            Each tuple is (command, passed) where passed is True if the test passed.
        pass_to_pass_after: Results of pass_to_pass tests after patch.
            Each tuple is (command, passed) where passed is True if the test passed.
        merge_conflict: Whether a merge conflict occurred when applying patch.
    """

    passed: bool
    reasons: list[str] = field(default_factory=list)
    fail_to_pass_before: list[tuple[str, bool]] = field(default_factory=list)
    fail_to_pass_after: list[tuple[str, bool]] = field(default_factory=list)
    pass_to_pass_after: list[tuple[str, bool]] = field(default_factory=list)
    merge_conflict: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Protocol
# ─────────────────────────────────────────────────────────────────────────────


class SandboxProtocol(Protocol):
    """Protocol for sandbox implementations used by DualCommitValidator."""

    async def run_command(
        self, cmd: str, *, timeout: float | None = None
    ) -> "ExecResultProtocol":
        """Execute a command in the sandbox."""
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Write a file to the sandbox."""
        ...


class ExecResultProtocol(Protocol):
    """Protocol for command execution results."""

    @property
    def exit_code(self) -> int: ...

    @property
    def stdout(self) -> str: ...

    @property
    def stderr(self) -> str: ...


# ─────────────────────────────────────────────────────────────────────────────
# DualCommitValidator Class
# ─────────────────────────────────────────────────────────────────────────────


class DualCommitValidator:
    """Validates SWE tasks using the dual-commit pattern.

    The dual-commit validation ensures that:
    1. fail_to_pass tests FAIL on the base commit (before patch)
    2. fail_to_pass tests PASS after applying the patch
    3. pass_to_pass tests PASS after applying the patch

    Example:
        validator = DualCommitValidator()
        result = await validator.validate(task, sandbox)
        if result.passed:
            print("Validation successful!")
        else:
            print(f"Validation failed: {result.reasons}")
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 120.0,
        patch_timeout_seconds: float = 30.0,
    ):
        """Initialize DualCommitValidator.

        Args:
            timeout_seconds: Timeout for test command execution.
            patch_timeout_seconds: Timeout for git apply operations.
        """
        self._timeout_seconds = timeout_seconds
        self._patch_timeout_seconds = patch_timeout_seconds

    async def validate(
        self,
        task: "SweTask",
        sandbox: SandboxProtocol,
    ) -> DualCommitResult:
        """Validate a SWE task using dual-commit validation.

        This method performs the following steps:
        1. Checkout base_commit
        2. Write test files (if test_patch provided)
        3. Run fail_to_pass tests → should FAIL
        4. Apply patch
        5. Run fail_to_pass tests → should PASS
        6. Run pass_to_pass tests → should PASS
        7. Revert to base commit

        Args:
            task: The SWE task to validate.
            sandbox: Sandbox running the repository.

        Returns:
            DualCommitResult with validation outcome and details.
        """
        reasons: list[str] = []
        fail_to_pass_before: list[tuple[str, bool]] = []
        fail_to_pass_after: list[tuple[str, bool]] = []
        pass_to_pass_after: list[tuple[str, bool]] = []
        merge_conflict = False

        # Step 1: Checkout base commit
        logger.info(f"Checking out base commit: {task.base_commit}")
        checkout_result = await sandbox.run_command(
            f"git checkout {task.base_commit}",
            timeout=self._patch_timeout_seconds,
        )
        if checkout_result.exit_code != 0:
            reasons.append(
                f"Failed to checkout base commit {task.base_commit}: "
                f"{checkout_result.stderr}"
            )
            return DualCommitResult(
                passed=False,
                reasons=reasons,
                merge_conflict=False,
            )

        # Step 2: Apply test patch if provided (writes test files)
        if task.test_patch:
            logger.info("Applying test patch")
            test_patch_result = await self._apply_patch(sandbox, task.test_patch)
            if not test_patch_result.success:
                # Test patch application failed - this may be expected in some cases
                logger.warning(
                    f"Test patch application failed: {test_patch_result.error}"
                )
                # Continue anyway - the test_patch may have been applied previously

        # Step 3: Run fail_to_pass tests on base commit (should FAIL)
        logger.info("Running fail_to_pass tests on base commit (expecting failures)")
        for cmd in task.fail_to_pass:
            try:
                result = await sandbox.run_command(cmd, timeout=self._timeout_seconds)
                failed_as_expected = result.exit_code != 0
                fail_to_pass_before.append((cmd, failed_as_expected))
                if not failed_as_expected:
                    reasons.append(
                        f"fail_to_pass test already passes on base commit: {cmd}"
                    )
            except Exception as e:
                # Treat exception as failure (which is expected)
                fail_to_pass_before.append((cmd, True))
                logger.warning(
                    f"Test command raised exception (treating as failure): {e}"
                )

        # Step 4: Apply the main patch
        logger.info("Applying main patch")
        patch_result = await self._apply_patch(sandbox, task.patch)

        if not patch_result.success:
            reasons.append(f"Failed to apply patch: {patch_result.error}")
            merge_conflict = patch_result.merge_conflict
            return DualCommitResult(
                passed=False,
                reasons=reasons,
                fail_to_pass_before=fail_to_pass_before,
                merge_conflict=merge_conflict,
            )

        # Step 5: Run fail_to_pass tests after patch (should PASS)
        logger.info("Running fail_to_pass tests after patch (expecting passes)")
        for cmd in task.fail_to_pass:
            try:
                result = await sandbox.run_command(cmd, timeout=self._timeout_seconds)
                passed = result.exit_code == 0
                fail_to_pass_after.append((cmd, passed))
                if not passed:
                    reasons.append(
                        f"fail_to_pass test failed after patch: {cmd} "
                        f"(exit={result.exit_code})"
                    )
            except Exception as e:
                fail_to_pass_after.append((cmd, False))
                reasons.append(f"fail_to_pass test error after patch: {cmd} - {e}")

        # Step 6: Run pass_to_pass tests after patch (should PASS)
        logger.info("Running pass_to_pass tests after patch (expecting passes)")
        for cmd in task.pass_to_pass:
            try:
                result = await sandbox.run_command(cmd, timeout=self._timeout_seconds)
                passed = result.exit_code == 0
                pass_to_pass_after.append((cmd, passed))
                if not passed:
                    reasons.append(
                        f"pass_to_pass test failed after patch: {cmd} "
                        f"(exit={result.exit_code})"
                    )
            except Exception as e:
                pass_to_pass_after.append((cmd, False))
                reasons.append(f"pass_to_pass test error after patch: {cmd} - {e}")

        # Determine overall passed status
        passed = len(reasons) == 0

        # Log summary
        if passed:
            logger.info("Dual-commit validation passed")
        else:
            logger.warning(f"Dual-commit validation failed: {reasons}")

        return DualCommitResult(
            passed=passed,
            reasons=reasons,
            fail_to_pass_before=fail_to_pass_before,
            fail_to_pass_after=fail_to_pass_after,
            pass_to_pass_after=pass_to_pass_after,
            merge_conflict=merge_conflict,
        )

    async def _apply_patch(
        self, sandbox: SandboxProtocol, patch: str
    ) -> "_PatchResult":
        """Apply a patch to the repository.

        Tries multiple strategies:
        1. git apply --allow-empty (handles empty patches)
        2. git apply --3way (handles conflicts with 3-way merge)

        Args:
            sandbox: The sandbox to apply the patch in.
            patch: The patch content to apply.

        Returns:
            _PatchResult with success status and error message if failed.
        """
        if not patch or not patch.strip():
            # Empty patch is considered success
            return _PatchResult(success=True)

        # Write patch to a temp file
        patch_file = ".dual_commit_patch.tmp"
        try:
            await sandbox.write_file(patch_file, patch)
        except Exception as e:
            return _PatchResult(
                success=False,
                error=f"Failed to write patch file: {e}",
                merge_conflict=False,
            )

        # Try git apply --allow-empty first
        result = await sandbox.run_command(
            f"git apply --allow-empty {patch_file}",
            timeout=self._patch_timeout_seconds,
        )

        if result.exit_code == 0:
            await sandbox.run_command(f"rm -f {patch_file}")
            return _PatchResult(success=True)

        is_conflict = (
            "conflict" in result.stderr.lower()
            or "conflict" in result.stdout.lower()
            or "does not apply" in result.stderr.lower()
            or "does not apply" in result.stdout.lower()
        )

        result_3way = await sandbox.run_command(
            f"git apply --3way {patch_file} 2>&1 || true",
            timeout=self._patch_timeout_seconds,
        )

        is_conflict = is_conflict or (
            "conflict" in result_3way.stdout.lower()
            or "conflict" in result_3way.stderr.lower()
            or "does not apply" in result_3way.stdout.lower()
            or "does not apply" in result_3way.stderr.lower()
        )

        # Cleanup
        await sandbox.run_command(f"rm -f {patch_file}")

        # For --3way, check if files were modified despite warnings
        check_result = await sandbox.run_command(
            "git status --porcelain",
            timeout=self._patch_timeout_seconds,
        )

        if check_result.exit_code == 0 and check_result.stdout.strip():
            # There are modified files, so patch probably applied
            logger.info(
                f"Patch applied with --3way, modified files: {check_result.stdout}"
            )
            return _PatchResult(success=True)

        return _PatchResult(
            success=False,
            error=f"git apply failed: {result.stderr or result_3way.stdout}",
            merge_conflict=is_conflict,
        )


@dataclass
class _PatchResult:
    """Internal result of patch application."""

    success: bool
    error: str | None = None
    merge_conflict: bool = False
