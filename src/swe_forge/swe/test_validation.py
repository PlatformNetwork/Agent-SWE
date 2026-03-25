"""Test validation logic for generated test commands.

This module provides the TestValidator class for validating generated tests,
including:
- Running tests in a sandbox to verify pass/fail behavior
- Detecting string-matching anti-patterns
- Ensuring tests don't leak solutions
- Script validation

This module reuses and extends the validation logic from test_generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Protocol

from swe_forge.swe.test_generator import TestFile

if TYPE_CHECKING:
    pass

logger = getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    valid: bool
    reasons: list[str] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# String-Matching Detection Patterns
# ─────────────────────────────────────────────────────────────────────────────

STRING_MATCHING_PATTERNS: list[tuple[str, str]] = [
    # Python source-reading patterns
    (r"open\([^)]*\)\.read", "open().read() used to read source files"),
    (r"Path\([^)]*\)\.read_text", "Path().read_text() used to read source files"),
    (r"\.read\(\)[^;]*assert.*\bin\b", ".read() + assert...in (string-matching)"),
    # JavaScript/TypeScript source-reading patterns
    (r"readFileSync\(", "readFileSync() used to read source files"),
    (r"readFile\(", "readFile() used to read source files"),
    # Combined read + assert patterns
    (
        r"assert.*\bin\s+(source|content|text|code|file_content|src|contents)",
        "assert...in source/content (string-matching on file content)",
    ),
    (r"\.(includes|contains)\(['\"]", ".includes()/.contains() on source content"),
    # Additional anti-patterns for string matching
    (r'assert\s*["\']', 'assert "..." (string literal assertion)'),
    (r'assert\s*\(["\'][^"\']+["\']\s*\)', "assert('...') with string literal"),
    # Solution leaking patterns
    (r"#\s*solution", "Solution comment found"),
    (r"//\s*solution", "Solution comment found"),
    (r"#\s*ANSWER", "Answer comment found"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Protocol
# ─────────────────────────────────────────────────────────────────────────────


class SandboxProtocol(Protocol):
    """Protocol for sandbox implementations used by TestValidator."""

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
# Detection Functions
# ─────────────────────────────────────────────────────────────────────────────


def detect_string_matching(test_content: str) -> list[str]:
    """Detect string-matching anti-patterns in test content.

    Returns list of violation descriptions.
    """
    violations: list[str] = []

    for pattern, description in STRING_MATCHING_PATTERNS:
        try:
            matches = list(re.finditer(pattern, test_content))
            if matches:
                violations.append(f"{description} ({len(matches)} occurrence(s))")
        except re.error:
            continue

    return violations


def detect_solution_leak(test_content: str) -> list[str]:
    """Detect if test content leaks solution information.

    Returns list of violation descriptions.
    """
    violations: list[str] = []

    # Check for hardcoded answers/solutions
    solution_patterns = [
        (r"#\s*solution\s*:", "Hardcoded solution comment"),
        (r"//\s*solution\s*:", "Hardcoded solution comment"),
        (
            r"expected\s*=\s*['\"][^'\"]{20,}['\"]",
            "Hardcoded expected output (>20 chars)",
        ),
        (r"return\s+[''][^'']{20,}['']", "Hardcoded return value (>20 chars)"),
    ]

    for pattern, description in solution_patterns:
        try:
            if re.search(pattern, test_content, re.IGNORECASE):
                violations.append(description)
        except re.error:
            continue

    return violations


def validate_script_structure(files: list[TestFile]) -> list[str]:
    """Validate test scripts for structural issues.

    Returns list of issue descriptions.
    """
    issues: list[str] = []
    known_paths: set[str] = {f.path for f in files}

    for file in files:
        is_shell = file.path.endswith((".sh", ".bash"))

        if is_shell:
            trimmed = file.content.lstrip()
            if not trimmed.startswith("#!"):
                issues.append(
                    f"Shell script '{file.path}' is missing a shebang line (e.g. #!/bin/bash)"
                )

            if not file.content.strip():
                issues.append(f"Shell script '{file.path}' is empty")

        # Check for references to missing test files
        for line in file.content.splitlines():
            trimmed = line.strip()
            for token in trimmed.split():
                if (
                    token.startswith("tests/") or token.startswith("./tests/")
                ) and token.endswith((".py", ".js", ".ts", ".sh")):
                    normalized = token.removeprefix("./")
                    if normalized not in known_paths:
                        issues.append(
                            f"File '{file.path}' references '{normalized}' which was not submitted"
                        )

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# TestValidator Class
# ─────────────────────────────────────────────────────────────────────────────


class TestValidator:
    """Validates generated test commands.

    The TestValidator runs tests in a sandbox, checks for anti-patterns,
    and ensures tests use proper behavioral testing.

    Example:
        validator = TestValidator()
        result = await validator.validate_tests(
            commands=["pytest test_feature.py"],
            test_files=[TestFile(path="test_feature.py", content="...")],
            sandbox=my_sandbox,
        )
        if result.valid:
            print(f"All tests passed: {result.passed}")
    """

    def __init__(
        self,
        *,
        check_string_matching: bool = True,
        check_solution_leak: bool = True,
        check_script_structure: bool = True,
        timeout_seconds: float = 120.0,
    ):
        """Initialize TestValidator.

        Args:
            check_string_matching: Whether to check for string-matching anti-patterns.
            check_solution_leak: Whether to check for solution leaks.
            check_script_structure: Whether to check script structure.
            timeout_seconds: Default timeout for test execution.
        """
        self._check_string_matching = check_string_matching
        self._check_solution_leak = check_solution_leak
        self._check_script_structure = check_script_structure
        self._timeout_seconds = timeout_seconds

    async def validate_tests(
        self,
        commands: list[str],
        test_files: list[TestFile] | None = None,
        sandbox: SandboxProtocol | None = None,
    ) -> ValidationResult:
        """Validate test commands.

        This method:
        1. Checks for string-matching anti-patterns in test files
        2. Checks for solution leaks
        3. Validates script structure
        4. Runs tests in sandbox (if provided) and collects results

        Args:
            commands: List of test commands to validate.
            test_files: Optional list of test files for static analysis.
            sandbox: Optional sandbox for running tests.

        Returns:
            ValidationResult with validation outcome and details.
        """
        reasons: list[str] = []
        passed: list[str] = []
        failed: list[str] = []

        # Static analysis on test files
        if test_files:
            # Check for string-matching anti-patterns
            if self._check_string_matching:
                for tf in test_files:
                    violations = detect_string_matching(tf.content)
                    if violations:
                        reasons.append(
                            f"File '{tf.path}' has string-matching anti-patterns: "
                            + "; ".join(violations)
                        )

            # Check for solution leaks
            if self._check_solution_leak:
                for tf in test_files:
                    violations = detect_solution_leak(tf.content)
                    if violations:
                        reasons.append(
                            f"File '{tf.path}' may leak solution: "
                            + "; ".join(violations)
                        )

            # Check script structure
            if self._check_script_structure:
                issues = validate_script_structure(test_files)
                reasons.extend(issues)

        # Run tests in sandbox if provided
        if sandbox and commands:
            for cmd in commands:
                try:
                    result = await sandbox.run_command(
                        cmd, timeout=self._timeout_seconds
                    )
                    if result.exit_code == 0:
                        passed.append(cmd)
                    else:
                        failed.append(cmd)
                        reasons.append(
                            f"Test command failed (exit={result.exit_code}): {cmd}"
                        )
                except Exception as e:
                    failed.append(cmd)
                    reasons.append(f"Test command error: {cmd} - {e}")

        # Determine overall validity
        valid = len(reasons) == 0

        return ValidationResult(
            valid=valid,
            reasons=reasons,
            passed=passed,
            failed=failed,
        )

    async def validate_fail_to_pass(
        self,
        commands: list[str],
        test_files: list[TestFile] | None,
        sandbox: SandboxProtocol,
    ) -> ValidationResult:
        """Validate fail_to_pass tests should FAIL on base commit.

        fail_to_pass tests are expected to FAIL on the base commit
        (before PR patch) and PASS after the patch is applied.

        Args:
            commands: List of fail_to_pass test commands.
            test_files: Test files for static analysis.
            sandbox: Sandbox running on base commit.

        Returns:
            ValidationResult. Tests should FAIL for valid result.
        """
        reasons: list[str] = []
        passed: list[str] = []
        failed: list[str] = []

        # Run static analysis first
        if test_files and self._check_string_matching:
            for tf in test_files:
                violations = detect_string_matching(tf.content)
                if violations:
                    reasons.append(
                        f"File '{tf.path}' has string-matching anti-patterns: "
                        + "; ".join(violations)
                    )

        # Run tests - they should FAIL on base commit
        for cmd in commands:
            try:
                result = await sandbox.run_command(cmd, timeout=self._timeout_seconds)
                if result.exit_code != 0:
                    # Test failed as expected
                    failed.append(
                        cmd
                    )  # Note: 'failed' means it failed execution, which is expected here
                else:
                    # Test passed when it should have failed
                    passed.append(cmd)
                    reasons.append(
                        f"fail_to_pass test already passes on base commit: {cmd}"
                    )
            except Exception as e:
                reasons.append(f"Test command error: {cmd} - {e}")

        # For fail_to_pass, valid means tests FAILED (as expected on base)
        valid = (
            len(
                [
                    r
                    for r in reasons
                    if "string-matching" not in r and "error" not in r.lower()
                ]
            )
            == 0
        )

        return ValidationResult(
            valid=valid,
            reasons=reasons,
            passed=passed,
            failed=failed,
        )

    async def validate_pass_to_pass(
        self,
        commands: list[str],
        sandbox: SandboxProtocol,
    ) -> ValidationResult:
        """Validate pass_to_pass tests should PASS.

        pass_to_pass tests are expected to PASS on both base and
        patched commits.

        Args:
            commands: List of pass_to_pass test commands.
            sandbox: Sandbox to run tests in.

        Returns:
            ValidationResult. Tests should PASS for valid result.
        """
        reasons: list[str] = []
        passed: list[str] = []
        failed: list[str] = []

        for cmd in commands:
            try:
                result = await sandbox.run_command(cmd, timeout=self._timeout_seconds)
                if result.exit_code == 0:
                    passed.append(cmd)
                else:
                    failed.append(cmd)
                    reasons.append(
                        f"pass_to_pass test failed: {cmd} (exit={result.exit_code})"
                    )
            except Exception as e:
                failed.append(cmd)
                reasons.append(f"Test command error: {cmd} - {e}")

        # For pass_to_pass, valid means all tests PASSED
        valid = len(failed) == 0

        return ValidationResult(
            valid=valid,
            reasons=reasons,
            passed=passed,
            failed=failed,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────


def reject_string_matching_tests(files: list[TestFile]) -> str | None:
    """Scan test files for string-matching anti-patterns.

    Returns rejection reason if forbidden patterns are found, None otherwise.
    This is a convenience function for backward compatibility with test_generator.
    """
    violations: list[str] = []

    for file in files:
        content = file.content

        # Use the original patterns from test_generator for compatibility
        original_patterns: list[tuple[str, str]] = [
            (r"open\([^)]*\)\.read", "open().read() used to read source files"),
            (
                r"Path\([^)]*\)\.read_text",
                "Path().read_text() used to read source files",
            ),
            (
                r"\.read\(\)[^;]*assert.*\bin\b",
                ".read() + assert...in (string-matching)",
            ),
            (r"readFileSync\(", "readFileSync() used to read source files"),
            (r"readFile\(", "readFile() used to read source files"),
            (
                r"assert.*\bin\s+(source|content|text|code|file_content|src|contents)",
                "assert...in source/content (string-matching on file content)",
            ),
            (
                r"\.(includes|contains)\(['\"]",
                ".includes()/.contains() on source content",
            ),
        ]

        for pattern, description in original_patterns:
            try:
                matches = list(re.finditer(pattern, content))
                if matches:
                    # Check if this is actually testing source files
                    has_behavioral = any(
                        kw in content
                        for kw in ["import ", "require(", "from ", "fetch(", "request("]
                    )

                    # Count assertions
                    total_asserts = (
                        content.count("assert")
                        + content.count("expect(")
                        + content.count("Assert.")
                    )
                    string_match_count = len(matches)

                    # Reject if >50% of assertions are string-matching or no behavioral patterns
                    if total_asserts > 0 and (
                        string_match_count * 2 > total_asserts or not has_behavioral
                    ):
                        violations.append(
                            f"File '{file.path}': {description} "
                            f"({string_match_count} of {total_asserts} assertions)"
                        )
            except re.error:
                continue

    if not violations:
        return None

    return "Your tests use forbidden source-reading patterns:\n- " + "\n- ".join(
        violations
    )


def validate_test_scripts(files: list[TestFile]) -> str | None:
    """Validate generated test scripts for structural issues.

    Returns issue description if validation fails, None otherwise.
    This is a convenience function for backward compatibility with test_generator.
    """
    issues = validate_script_structure(files)

    if not issues:
        return None

    return "Test script validation issues:\n- " + "\n- ".join(issues)
