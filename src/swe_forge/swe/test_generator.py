"""Agentic test generator with multi-turn LLM loop.

This module provides the TestGenerator class that runs an agentic LLM loop
to generate test commands for SWE tasks. The agent explores the codebase,
installs dependencies, writes tests, and validates them.

Key features:
- TurnLimit enforcement (max 200 turns by default)
- Tool-based interaction (shell, submit_tests, write_file, etc.)
- Validation of generated tests (string-matching rejection)
- Mock-friendly design for unit testing
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
from contextvars import ContextVar
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any, Protocol

from swe_forge.llm.client import (
    GenerationRequest,
    LLMClient,
    ToolCall,
    ToolDefinition,
)
from swe_forge.llm.tools import (
    AgenticLoop,
    ShellArgs,
)

if TYPE_CHECKING:
    from swe_forge.swe.models import SweTask

logger = getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_AGENT_TURNS = 400

# ContextVars for per-async-task isolation
_dataset_prompt_var: ContextVar[str] = ContextVar("dataset_prompt", default="")
_written_files_var: ContextVar[list] = ContextVar("written_files", default=[])
_task_var: ContextVar = ContextVar("task", default=None)
_validation_retry_count_var: ContextVar[int] = ContextVar("validation_retry_count", default=0)
MAX_VALIDATION_RETRIES = 10
DEFAULT_TIMEOUT_MS = 60_000
PRE_APPLY_TIMEOUT_SECONDS = 180  # 180s timeout for pre-apply test validation
POST_APPLY_TIMEOUT_SECONDS = 180  # 180s timeout for post-apply test validation

KNOWN_REPO_PATTERNS = [
    "glassflow-api",
    "pydantic-",
    "sgl-project",
    "rust-skia",
    "python/cpython",
    "microsoft/",
    "google/",
    "facebook/",
]


def _get_progressive_hint(error_type: str, retry_count: int) -> str:
    """Get progressive hint based on retry count and error type.

    Tier 1 (1-3 retries): Generic guidance
    Tier 2 (4-6 retries): Specific hints based on error type
    Tier 3 (7-10 retries): Simplification suggestions

    Args:
        error_type: Type of error encountered
        retry_count: Current retry attempt number

    Returns:
        Progressive hint message
    """
    # Tier 3: Simplification hints (7-10 retries)
    if retry_count > 6:
        return (
            "STRUGGLING? Try a SIMPLER test approach:\n"
            "• Import the module and call the function directly\n"
            "• Check basic input/output behavior\n"
            "• Focus on ONE specific bug behavior\n"
            "• Avoid complex setup or dependencies"
        )

    # Tier 2: Specific hints based on error type (4-6 retries)
    if retry_count > 3:
        if "string-matching" in error_type.lower():
            return (
                "STRING-MATCHING REJECTED: Do NOT read source files!\n"
                "• Import the module with 'import package.module'\n"
                "• Call functions and check return values\n"
                "• Use assert result == expected, NOT assert 'code' in file_content"
            )
        elif "passed on base" in error_type.lower() or "pass" in error_type.lower():
            return (
                "TEST PASSES ON BASE: This doesn't test the bug!\n"
                "• The test MUST fail before the patch is applied\n"
                "• Check that you're testing the exact bug scenario\n"
                "• Ensure the test actually exercises the buggy code path"
            )
        elif "failed after patch" in error_type.lower():
            return (
                "TEST FAILS AFTER PATCH: Patch doesn't fix this behavior!\n"
                "• Your test may be checking unrelated behavior\n"
                "• Verify the patch actually changes what you're testing\n"
                "• Focus on testing the specific change in the patch"
            )
        elif "timeout" in error_type.lower():
            return (
                "TEST TIMEOUT: Test takes too long!\n"
                "• Use smaller test cases or inputs\n"
                "• Mock slow operations if needed\n"
                "• Focus on unit tests, not integration tests"
            )
        else:
            return (
                "VALIDATION FAILED: Check your test approach:\n"
                "• Verify imports work correctly\n"
                "• Ensure test commands are appropriate for the language\n"
                "• Check that test files are in the correct location"
            )

    # Tier 1: Generic hints (1-3 retries)
    return (
        "Check your test structure and imports. "
        "Ensure tests follow best practices for the language and test framework."
    )


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Generate behavioral tests for a software bug fix.

## BUDGET AWARENESS

You have a limited number of turns. Be efficient. Try the simplest test approach first.
Don't spend many turns installing complex dependencies. Use the pre-installed language toolchain.
Aim to submit tests within 10-15 turns.

## YOUR MISSION

Generate tests that:
1. FAIL on base commit (proves bug exists)
2. PASS after applying patch (proves fix works)

## WORKSPACE

- Repository: /workspace/repo/ (checked out at the base commit, BEFORE the fix)
- Patch: /workspace/forge/patch.diff (the fix that was applied)

## PHASE 1: DISCOVERY (MANDATORY FIRST STEP)

You MUST discover the project structure BEFORE writing any tests:

1. DETECT LANGUAGE:
   - List files in /workspace/repo to find package files
   - Python: pyproject.toml, setup.py, requirements.txt, setup.cfg
   - JavaScript/TypeScript: package.json, tsconfig.json
   - Rust: Cargo.toml
   - Go: go.mod, go.sum
   - Java: pom.xml, build.gradle, build.gradle.kts
   - Ruby: Gemfile, Rakefile
   - PHP: composer.json

2. DISCOVER TEST FRAMEWORK:
   - Read package files to find test dependencies
   - Python: look for pytest, unittest, nose in requirements
   - JavaScript: look for jest, mocha, vitest in package.json
   - Rust: tests in Cargo.toml, use `cargo test`
   - Go: _test.go files, use `go test`
   - Java: junit dependency, use `mvn test` or `gradle test`

3. DISCOVER TEST LOCATION:
   - Python: tests/ or test_ directories, test_*.py files
   - JavaScript: tests/, test/, __tests__/, *.test.js, *.spec.js
   - Rust: tests/ directory, #[test] in src/
   - Go: *_test.go files alongside source
   - Java: src/test/java/

4. DISCOVER INSTALL COMMANDS:
   - Read package files, Makefile, README, CI configs (.github/workflows/)
   - Try commands and verify exit code 0
   - DO NOT guess - DISCOVER by trying

## PHASE 2: PATCH ANALYSIS

After discovering the project structure, analyze the patch to understand the bug:

1. Read the patch: shell("cat /workspace/forge/patch.diff")
2. Identify CHANGED FILES from the diff headers (diff --git a/... b/...)
3. For each changed file, use read_file() to examine the full context of changes
4. Identify CHANGED FUNCTIONS/METHODS - what specific functions were modified?
5. Determine the BEHAVIORAL DIFFERENCE:
   - BEFORE the patch: what was the broken behavior? (exception, wrong output, missing feature)
   - AFTER the patch: what is the correct behavior?
6. This behavioral difference is EXACTLY what your test must exercise

## PHASE 3: TEST GENERATION

1. set_dataset_prompt("Brief description of what changed")
2. Write a test that exercises the BROKEN behavior:
   - Import/require the affected module
   - Call the changed function with inputs that trigger the bug
   - Assert the CORRECT (post-fix) behavior
3. Verify the test runs (syntax check): shell("pytest tests/test_fix.py --collect-only") or equivalent
4. Submit with submit_tests() - it automatically validates:
   - Runs your fail_to_pass tests on base commit (must FAIL)
   - Applies the patch
   - Runs your fail_to_pass tests again (must PASS)

NOTE: You do NOT need to manually apply or revert the patch. submit_tests() handles this automatically.

## VALIDATION RULES

When you call submit_tests(), it automatically:
  (a) Runs fail_to_pass on base commit — tests must FAIL
  (b) Applies the patch
  (c) Runs fail_to_pass again — tests must PASS

- `install_commands` is REQUIRED and must be non-empty (e.g., ["pip install -e ."])
- String-matching tests (reading source files and asserting content) are REJECTED
- You get up to 10 retry attempts if validation fails

## COMMON FAILURES AND RECOVERY

- ImportError → install the missing package first (e.g., shell("pip install package"))
- ModuleNotFoundError → check if you need `pip install -e .` or the project uses a virtualenv
- Test PASSES on base (should fail) → your test doesn't exercise the bug; rethink what behavior changed
- Test FAILS after patch (should pass) → your test assertion is wrong; check the actual post-fix behavior
- Timeout → simplify the test, use smaller inputs, avoid integration tests

## CRITICAL RULES

- NEVER assume test commands - DISCOVER them
- NEVER assume test directory - FIND what the project uses
- Follow existing test patterns in the repository
- Test MUST fail before patch, pass after patch
- If unsure, read existing test files in the repo for patterns

## FEW-SHOT PATTERNS (language-agnostic)

### Pattern 1: Behavior Changed - Output/Message Different
BEFORE PATCH: function returns "Error: X"
AFTER PATCH: function returns "Error: Y"
TEST: call function, assert it returns "Y" (fails before, passes after)

### Pattern 2: Bug Fixed - Previously Broken Feature Now Works
BEFORE PATCH: feature X throws exception
AFTER PATCH: feature X works correctly
TEST: use feature X, expect success (fails before, passes after)

### Pattern 3: Logic Fixed - Calculation/Transformation Corrected
BEFORE PATCH: calculate(10) returns 20
AFTER PATCH: calculate(10) returns 10
TEST: assert calculate(10) == 10 (fails before, passes after)

### Pattern 4: Validation Added - Previously Invalid Now Rejected
BEFORE PATCH: invalid input accepted
AFTER PATCH: invalid input rejected
TEST: expect rejection on invalid input (fails before, passes after)

## END-TO-END EXAMPLE WORKFLOW

Example workflow showing the complete tool call sequence:
1. shell("cat /workspace/forge/patch.diff") → understand what changed
2. shell("cat pyproject.toml") → find test framework
3. read_file("src/module.py") → understand the changed function
4. write_file("tests/test_fix.py", "import pytest\\n...") → write test
5. shell("pip install -e . && pytest tests/test_fix.py --collect-only") → verify syntax
6. set_dataset_prompt("Fix divide by zero in calculate()")
7. submit_tests(fail_to_pass=["pytest tests/test_fix.py -v"], install_commands=["pip install -e ."])

## SUBMISSION FORMAT

install_commands: ["apt-get update", "apt-get install -y python3", ...]
fail_to_pass: ["pytest tests/test_feature.py", "cargo test test_feature", "go test ./...", "npm test"]
pass_to_pass: [] (optional tests that should keep passing)

## FEW-SHOT EXAMPLES

### Example 1: Python pytest - API Response Storage Bug
# Bug: Responses with store=False were incorrectly retrievable
def test_store_false_not_retrievable():
    # FAILS before patch, PASSES after
    stream = client.create(input="Hello", store=False)
    response_id = next(c.id for c in stream if c.type == "created")
    with pytest.raises(Exception):  # BUG: was retrievable
        client.retrieve(response_id)

### Example 2: Python pytest - Config Defaults Override Bug
# Bug: Defaults overrode explicit config values
def test_explicit_values_preserved():
    # FAILS before patch, PASSES after
    cfg = Config(timeout=30)  # explicit value
    cfg.apply_defaults(Defaults(timeout=60))
    assert cfg.timeout == 30  # BUG: returned 60

### Example 3: TypeScript Jest - State Not Rendering Bug
// Bug: UI state updates weren't reflecting in renders
it('updates name after edit', async () => {
    // FAILS before patch, PASSES after
    render(<Profile name="Alice" />);
    await user.click(screen.getByText('Edit'));
    await user.type(screen.getByLabelText('Name'), 'Bob');
    await screen.findByText('Bob');  // BUG: showed "Alice"
});

### Example 4: TypeScript Jest - Validation Not Showing Bug
// Bug: Error message not displayed for invalid input
it('shows error for duplicate email', async () => {
    // FAILS before patch, PASSES after
    render(<RegisterForm validateEmail={mockReject} />);
    await user.type(screen.getByLabelText('Email'), 'dup@test.com');
    await screen.findByText('Already registered');  // BUG: no error
});
"""


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TestFile:
    """A test file generated by the agent."""

    path: str
    content: str


@dataclass
class GeneratedTests:
    """Result of test generation.

    Attributes:
        fail_to_pass: Test commands that FAIL on base commit, PASS after PR patch.
        pass_to_pass: Test commands that PASS on both base and PR commit.
        test_files: Test files written by the agent.
        install_commands: Shell commands that successfully installed dependencies.
        dataset_prompt: Natural language description of the PR changes (LLM generated).
        turn_count: Number of turns used during generation.
        success: Whether generation was successful.
    """

    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    test_files: list[TestFile] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    dataset_prompt: str = ""
    turn_count: int = 0
    success: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Protocol
# ─────────────────────────────────────────────────────────────────────────────


class SandboxProtocol(Protocol):
    """Protocol for sandbox implementations used by TestGenerator."""

    async def run_command(
        self, cmd: str, *, timeout: float | None = None
    ) -> "ExecResultProtocol":
        """Execute a command in the sandbox."""
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Write a file to the sandbox."""
        ...

    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox."""
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
# Tool Schemas
# ─────────────────────────────────────────────────────────────────────────────


def write_file_tool_schema() -> ToolDefinition:
    """Create the write_file tool schema."""
    return ToolDefinition.create(
        name="write_file",
        description="Create or overwrite a file in the repository. Use this to write test files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path in the repo (e.g. 'tests/test_new_feature.py')",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    )


def apply_patch_tool_schema() -> ToolDefinition:
    """Create the apply_patch tool schema."""
    return ToolDefinition.create(
        name="apply_patch",
        description="Apply a unified diff patch to modify files. Use standard unified diff format.",
        parameters={
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "Unified diff content to apply",
                },
            },
            "required": ["patch"],
        },
    )


def read_file_tool_schema() -> ToolDefinition:
    """Create the read_file tool schema."""
    return ToolDefinition.create(
        name="read_file",
        description="Read a file from the repository with line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed, optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (optional)",
                },
            },
            "required": ["path"],
        },
    )


def list_dir_tool_schema() -> ToolDefinition:
    """Create the list_dir tool schema."""
    return ToolDefinition.create(
        name="list_dir",
        description="List directory contents.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively (default: false)",
                },
            },
            "required": ["path"],
        },
    )


def grep_files_tool_schema() -> ToolDefinition:
    """Create the grep_files tool schema."""
    return ToolDefinition.create(
        name="grep_files",
        description="Search file contents with regex.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (optional, default: repo root)",
                },
            },
            "required": ["pattern"],
        },
    )


def search_files_tool_schema() -> ToolDefinition:
    """Create the search_files tool schema."""
    return ToolDefinition.create(
        name="search_files",
        description="Find files by glob pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.py', '**/*.test.js')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (optional, default: repo root)",
                },
            },
            "required": ["pattern"],
        },
    )


def show_patch_tool_schema() -> ToolDefinition:
    """Create the show_patch tool schema."""
    return ToolDefinition.create(
        name="show_patch",
        description="Show the complete patch/diff for the current task. Use this when you need to re-read the patch after context compaction.",
        parameters={"type": "object", "properties": {}, "required": []},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool Result Types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ShellOutput:
    """Result from a shell command execution."""

    stdout: str
    stderr: str
    exit_code: int


@dataclass
class SubmitResult:
    """Result from submit_tests tool."""

    fail_to_pass: list[str]
    pass_to_pass: list[str]
    test_files: list[TestFile]
    install_commands: list[str]


@dataclass
class ToolResult:
    """Result from a tool execution."""

    content: str
    is_error: bool = False
    submit_result: SubmitResult | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def _extract_changed_files(patch: str) -> list[str]:
    """Extract changed file paths from diff headers in a patch.

    Parses lines like 'diff --git a/path/to/file b/path/to/file' and returns
    unique file paths in order of appearance.

    Args:
        patch: Unified diff content.

    Returns:
        List of unique changed file paths.
    """
    if not patch:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            # Format: diff --git a/path b/path
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                path = parts[1].strip()
                if path and path not in seen:
                    seen.add(path)
                    result.append(path)
    return result


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
]


def reject_string_matching_tests(files: list[TestFile]) -> str | None:
    """Scan test files for string-matching anti-patterns.

    Returns rejection reason if forbidden patterns are found, None otherwise.
    """
    violations: list[str] = []

    for file in files:
        content = file.content
        for pattern, description in STRING_MATCHING_PATTERNS:
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

    if not issues:
        return None

    return "Test script validation issues:\n- " + "\n- ".join(issues)


def validate_test_path(
    path: str,
    task_repo: str,
    language: str = "python",
) -> tuple[bool, str]:
    """Validate that test file path is safe and matches task context.

    Args:
        path: Path the agent wants to write to.
        task_repo: The repository being processed (e.g., 'pydantic/pydantic').
        language: Repository language.

    Returns:
        Tuple of (is_valid, error_message).
        If is_valid is False, error_message explains why.
    """
    if not path:
        return (False, "Path cannot be empty")

    path_lower = path.lower()
    import os

    basename = os.path.basename(path_lower)
    is_test_file = (
        path_lower.startswith("tests/")
        or path_lower.startswith("test/")
        or "/tests/" in path_lower
        or basename.startswith("test")
        or basename.endswith("_test.py")
        or basename.endswith("_test.js")
        or basename.endswith("_test.ts")
    )
    if not is_test_file:
        return (
            False,
            f"Invalid path '{path}': test files must be in tests/ directory or start with 'test'",
        )

    for repo_pattern in KNOWN_REPO_PATTERNS:
        if repo_pattern in path and repo_pattern not in task_repo:
            return (
                False,
                f"Path '{path}' contains external repository reference '{repo_pattern}'. "
                f"Cross-contamination detected - this path is from a different repository.",
            )

    if path.startswith("/"):
        return (False, f"Path '{path}' is absolute - must be relative to workspace")

    if ".." in path:
        return (False, f"Path '{path}' contains '..' - path traversal not allowed")

    if language == "python" and not path.endswith(".py"):
        return (
            False,
            f"Path '{path}' missing .py extension for Python repository",
        )

    return (True, "")


def is_valid_test_content(content: str, language: str) -> tuple[bool, str]:
    """Validate test content matches expected language patterns.

    Args:
        content: Test file content.
        language: Expected language.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not content or not content.strip():
        return (False, "Test content is empty")

    content_lower = content.lower()

    if language not in ("go", "golang"):
        if "package " in content and "func Test" in content:
            return (
                False,
                "Go test patterns (package/func Test) found in non-Go repository",
            )
        if "testing.T" in content:
            return (
                False,
                "Go testing.T pattern found in non-Go repository",
            )

    if language == "python":
        has_import = "import " in content
        has_def_test = "def test_" in content or "def test" in content_lower
        has_class_test = "class test" in content_lower or "class Test" in content

        if not (has_import or has_def_test or has_class_test):
            return (
                False,
                "Python test must contain 'import', 'def test_', or 'class Test'",
            )

    elif language in ["javascript", "typescript", "js", "ts"]:
        has_describe = "describe(" in content or "describe." in content
        has_it = "it(" in content or "test(" in content
        has_expect = "expect(" in content

        if not (has_describe or has_it or has_expect):
            return (
                False,
                "JavaScript test must contain 'describe', 'it(', or 'expect('",
            )

    return (True, "")


# ─────────────────────────────────────────────────────────────────────────────
# TestGenerator Class
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerator:
    """Agentic test generator using LLM multi-turn conversation.

    The TestGenerator runs an agentic loop where an LLM:
    1. Explores the repository structure
    2. Installs dependencies
    3. Writes behavioral tests
    4. Validates tests pass/fail correctly
    5. Submits final test commands

    The generator supports both real Docker sandboxes and mock implementations
    for testing.

    Example:
        generator = TestGenerator(llm_client)
        result = await generator.generate_tests(task, sandbox)
        if result.success:
            print(f"Generated {len(result.fail_to_pass)} fail_to_pass tests")
    """

    def __init__(
        self,
        llm: LLMClient,
        *,
        max_turns: int = MAX_AGENT_TURNS,
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        max_context_tokens: int = 100000,
    ):
        """Initialize TestGenerator.

        Args:
            llm: LLM client for generation.
            max_turns: Maximum number of agent turns (default: 200).
            model: Model identifier to use.
            temperature: Generation temperature (default: 0.2).
            max_tokens: Maximum tokens per response (default: 2000).
            max_context_tokens: Maximum context tokens before compaction (default: 100k).
        """
        self._llm = llm
        self._max_turns = max_turns
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_context_tokens = max_context_tokens

    def _get_tools(self) -> list[ToolDefinition]:
        """Get all tool schemas for the agent."""
        from swe_forge.llm.tools import (
            shell_tool_schema,
            submit_tests_tool_schema,
            set_dataset_prompt_tool_schema,
        )

        return [
            shell_tool_schema(),
            submit_tests_tool_schema(),
            set_dataset_prompt_tool_schema(),
            read_file_tool_schema(),
            list_dir_tool_schema(),
            grep_files_tool_schema(),
            search_files_tool_schema(),
            write_file_tool_schema(),
            apply_patch_tool_schema(),
            show_patch_tool_schema(),
        ]

    def _truncate(self, s: str, max_len: int = 4000) -> str:
        """Truncate string to max length with ellipsis."""
        if len(s) <= max_len:
            return s
        return s[:max_len] + "..."

    def _smart_truncate(self, text: str, max_len: int) -> str:
        """Truncate text keeping beginning and end for pytest summary visibility."""
        if len(text) <= max_len:
            return text
        # Keep beginning (context) and end (pytest summary/errors)
        head = max_len // 4
        tail = max_len - head - 20
        return text[:head] + "\n... [truncated] ...\n" + text[-tail:]

    def _build_user_message(self, task: SweTask) -> str:
        """Build the initial user message for the agent."""
        parts: list[str] = []

        parts.append(f"""## Repository
- Repo: {task.repo}
- Language: {task.language}""")

        parts.append(f"""## Bug Description
{task.prompt or "No description provided"}""")

        # Add PR body if available
        pr_body = getattr(task, "original_pr_body", "") or ""
        pr_body = pr_body.strip()
        if pr_body:
            parts.append(f"""## PR Description
{self._truncate(pr_body, 2000)}""")

        # Extract changed files from diff headers
        changed_files = _extract_changed_files(task.patch)
        if changed_files:
            file_list = "\n".join(f"- {f}" for f in changed_files)
            parts.append(f"""## Changed Files
{file_list}""")

        parts.append(f"""## Patch (Changes Made)
{self._truncate(task.patch, 16000)}""")

        parts.append(
            "Generate tests that FAIL on this bug and PASS after applying the patch."
        )

        return "\n\n".join(parts)

    def _test_commands_for_language(self, language: str) -> tuple[list[str], list[str]]:
        """Get suggested build and test commands for a language.

        DEPRECATED: This method returns EMPTY LISTS. The agent MUST discover
        the actual commands by:
        1. Reading pyproject.toml, setup.py, package.json, etc.
        2. TRYING install commands and tracking which succeed (exit 0)
        3. TRYING test commands and tracking which work

        NO HARDCODED DEFAULTS - the LLM agent figures it out via tools.

        Use agentic_config.detect_repository_config() for real detection.
        """
        # NO DEFAULTS - agent must discover everything
        # Return empty lists as fallback - agent will populate via tools
        return ([], [])

    async def _execute_shell(
        self, args: ShellArgs, sandbox: SandboxProtocol
    ) -> ToolResult:
        """Execute a shell command in the sandbox."""
        timeout_sec = args.timeout_ms / 1000.0 if args.timeout_ms else None

        try:
            result = await sandbox.run_command(args.command, timeout=timeout_sec)
            stdout = self._smart_truncate(result.stdout, 8000)
            stderr = self._truncate(result.stderr, 3000)
            return ToolResult(
                content=f"Exit code: {result.exit_code}\n\nStdout:\n{stdout}\n\nStderr:\n{stderr}",
                is_error=result.exit_code != 0,
            )
        except Exception as e:
            return ToolResult(
                content=f"Error executing command: {e}",
                is_error=True,
            )

    async def _validate_pre_apply(
        self, tests: list[str], sandbox: SandboxProtocol
    ) -> tuple[bool, str]:
        """Validate that tests FAIL on base commit before patch applies.

        This ensures tests are actually testing the bug behavior, not just
        passing regardless of the patch.

        Args:
            tests: List of test commands to validate.
            sandbox: Sandbox for running tests.

        Returns:
            Tuple of (valid, error_message). valid=True if tests fail as expected.
        """
        if not tests:
            return False, "No tests to validate"

        # Run each test on base commit - they should all FAIL
        for test_cmd in tests:
            try:
                args = ShellArgs(
                    command=test_cmd,
                    timeout_ms=PRE_APPLY_TIMEOUT_SECONDS * 1000,
                )
                result = await asyncio.wait_for(
                    self._execute_shell(args, sandbox),
                    timeout=PRE_APPLY_TIMEOUT_SECONDS + 10,
                )

                if not result.is_error:
                    display_cmd = (
                        test_cmd if len(test_cmd) <= 50 else test_cmd[:47] + "..."
                    )
                    return False, (
                        f"Test '{display_cmd}' PASSED on base commit. "
                        "Tests must FAIL on base commit before patch applies. "
                        "This test does not test the bug behavior."
                    )
            except asyncio.TimeoutError:
                display_cmd = test_cmd if len(test_cmd) <= 50 else test_cmd[:47] + "..."
                logger.warning(
                    f"Pre-apply test timed out after {PRE_APPLY_TIMEOUT_SECONDS}s: {display_cmd}"
                )
                return False, (
                    f"TIMEOUT: Test '{display_cmd}' exceeded {PRE_APPLY_TIMEOUT_SECONDS}s. "
                    "Consider simpler test approach or reduce test scope."
                )
            except Exception as e:
                return False, f"Failed to run test '{test_cmd[:50]}': {e}"

        return True, ""

    async def _validate_post_apply(
        self, tests: list[str], patch: str, sandbox: SandboxProtocol
    ) -> tuple[bool, str]:
        """Validate that tests PASS after the patch is applied.

        This ensures the tests correctly test that the bug is fixed by the patch.

        Args:
            tests: List of test commands to validate.
            patch: The patch content to apply.
            sandbox: Sandbox for running tests.

        Returns:
            Tuple of (valid, error_message). valid=True if tests pass as expected.
        """
        if not tests:
            return False, "No tests to validate"

        if not patch:
            return False, "No patch provided for post-apply validation"

        applied = False
        try:
            await sandbox.write_file(".swe_forge_post_apply_patch.tmp", patch)
            result = await sandbox.run_command(
                "git apply --allow-empty .swe_forge_post_apply_patch.tmp"
            )
            if result.exit_code != 0:
                return False, f"Failed to apply patch: {result.stdout}"
            applied = True

            for test_cmd in tests:
                try:
                    args = ShellArgs(
                        command=test_cmd,
                        timeout_ms=POST_APPLY_TIMEOUT_SECONDS * 1000,
                    )
                    result = await asyncio.wait_for(
                        self._execute_shell(args, sandbox),
                        timeout=POST_APPLY_TIMEOUT_SECONDS + 10,
                    )

                    if result.is_error:
                        display_cmd = (
                            test_cmd if len(test_cmd) <= 50 else test_cmd[:47] + "..."
                        )
                        return False, (
                            f"Test '{display_cmd}' FAILED after patch. "
                            "Tests must PASS after the patch is applied. "
                            "The patch should fix the bug being tested."
                        )
                except asyncio.TimeoutError:
                    display_cmd = (
                        test_cmd if len(test_cmd) <= 50 else test_cmd[:47] + "..."
                    )
                    logger.warning(
                        f"Post-apply test timed out after {POST_APPLY_TIMEOUT_SECONDS}s: {display_cmd}"
                    )
                    return False, (
                        f"TIMEOUT: Test '{display_cmd}' exceeded {POST_APPLY_TIMEOUT_SECONDS}s. "
                        "Consider simpler test approach or reduce test scope."
                    )
                except Exception as e:
                    return False, f"Failed to run test '{test_cmd[:50]}': {e}"

            return True, ""

        finally:
            if applied:
                try:
                    await sandbox.run_command("git checkout . && git clean -fd")
                except Exception:
                    pass
                try:
                    await sandbox.run_command("rm -f .swe_forge_post_apply_patch.tmp")
                except Exception:
                    pass

    async def _handle_write_file(
        self,
        arguments: dict[str, Any],
        sandbox: SandboxProtocol,
        *,
        task_repo: str = "",
        language: str = "python",
    ) -> ToolResult:
        """Handle write_file tool call."""
        path = arguments.get("path", "")
        content = arguments.get("content", "")

        if not path:
            return ToolResult(content="Error: missing path parameter", is_error=True)

        is_valid, error_msg = validate_test_path(path, task_repo, language)
        if not is_valid:
            return ToolResult(content=f"Error: {error_msg}", is_error=True)

        is_valid_content, content_error = is_valid_test_content(content, language)
        if not is_valid_content:
            return ToolResult(content=f"Error: {content_error}", is_error=True)

        try:
            await sandbox.write_file(path, content)

            written_files = _written_files_var.get()
            for existing in written_files:
                if existing.path == path:
                    existing.content = content
                    break
            else:
                written_files.append(TestFile(path=path, content=content))

            logger.debug(f"Agent wrote file: {path} ({len(content)} bytes)")
            return ToolResult(content=f"File written: {path}")
        except Exception as e:
            return ToolResult(content=f"Failed to write {path}: {e}", is_error=True)

    async def _handle_read_file(
        self, arguments: dict[str, Any], sandbox: SandboxProtocol
    ) -> ToolResult:
        """Handle read_file tool call."""
        path = arguments.get("path", "")

        if not path:
            return ToolResult(content="Error: missing file path", is_error=True)

        try:
            content = await sandbox.read_file(path)

            lines = content.splitlines()
            offset = int(arguments.get("offset", 0))
            limit = int(arguments.get("limit", 200))
            selected_lines = lines[offset:offset + limit]
            numbered = "\n".join(
                f"{offset + i + 1}: {line}" for i, line in enumerate(selected_lines)
            )
            remaining = len(lines) - (offset + len(selected_lines))
            if remaining > 0:
                numbered += f"\n... [{remaining} more lines truncated]"

            return ToolResult(
                content=self._truncate(f"File: {path}\n\n{numbered}", 5000)
            )
        except Exception as e:
            return ToolResult(content=f"Failed to read {path}: {e}", is_error=True)

    async def _handle_tool_call(
        self,
        tool_call: ToolCall,
        sandbox: SandboxProtocol,
    ) -> ToolResult:
        """Handle a single tool call from the agent."""
        tool_name = tool_call.function.name

        try:
            arguments = (
                json.loads(tool_call.function.arguments)
                if tool_call.function.arguments
                else {}
            )
        except json.JSONDecodeError as e:
            return ToolResult(content=f"Invalid JSON arguments: {e}", is_error=True)

        logger.debug(f"Tool call: {tool_name} with args: {list(arguments.keys())}")

        if tool_name == "shell":
            try:
                args = ShellArgs(
                    command=arguments.get("command", ""),
                    timeout_ms=arguments.get("timeout_ms", DEFAULT_TIMEOUT_MS),
                )
                if not args.command:
                    return ToolResult(content="Error: missing command", is_error=True)
                return await self._execute_shell(args, sandbox)
            except Exception as e:
                return ToolResult(
                    content=f"Error parsing shell args: {e}", is_error=True
                )

        elif tool_name == "write_file":
            task = _task_var.get()
            return await self._handle_write_file(
                arguments,
                sandbox,
                task_repo=task.repo if task else "",
                language=task.language if task else "python",
            )

        elif tool_name == "read_file":
            return await self._handle_read_file(arguments, sandbox)

        elif tool_name == "list_dir":
            path = arguments.get("path", ".")
            try:
                result = await sandbox.run_command(f"ls -la {path}")
                return ToolResult(content=self._truncate(result.stdout, 3000))
            except Exception as e:
                return ToolResult(
                    content=f"Error listing directory: {e}", is_error=True
                )

        elif tool_name == "grep_files":
            pattern = arguments.get("pattern", "")
            path = arguments.get("path", ".")
            try:
                result = await sandbox.run_command(
                    f"grep -rn {shlex.quote(pattern)} {shlex.quote(path)} | head -100"
                )
                return ToolResult(content=self._truncate(result.stdout, 5000))
            except Exception as e:
                return ToolResult(content=f"Error grepping: {e}", is_error=True)

        elif tool_name == "search_files":
            pattern = arguments.get("pattern", "*")
            path = arguments.get("path", ".")
            try:
                result = await sandbox.run_command(
                    f"find {shlex.quote(path)} -name {shlex.quote(pattern)} | head -100"
                )
                return ToolResult(content=self._truncate(result.stdout, 2000))
            except Exception as e:
                return ToolResult(content=f"Error searching: {e}", is_error=True)

        elif tool_name == "apply_patch":
            patch = arguments.get("patch", "")
            if not patch:
                return ToolResult(content="Error: missing patch", is_error=True)
            try:
                # Write patch file and apply
                await sandbox.write_file(".swe_forge_tool_patch.tmp", patch)
                result = await sandbox.run_command(
                    "git apply --allow-empty .swe_forge_tool_patch.tmp && rm -f .swe_forge_tool_patch.tmp"
                )
                if result.exit_code == 0:
                    return ToolResult(content="Patch applied successfully.")
                return ToolResult(
                    content=f"git apply failed: {result.stdout}", is_error=True
                )
            except Exception as e:
                return ToolResult(content=f"Error applying patch: {e}", is_error=True)

        elif tool_name == "show_patch":
            task = _task_var.get()
            patch_content = task.patch if task else ""
            if not patch_content:
                return ToolResult(content="No patch available.", is_error=True)
            return ToolResult(content=patch_content)

        elif tool_name == "set_dataset_prompt":
            prompt = arguments.get("prompt", "")
            if prompt:
                _dataset_prompt_var.set(prompt)
                logger.info(f"Dataset prompt set: {prompt[:100]}")
                return ToolResult(content=f"Dataset prompt set: {prompt[:100]}")
            return ToolResult(content="Error: missing prompt", is_error=True)

        elif tool_name == "submit_tests":
            logger.info(
                f"submit_tests called with: fail_to_pass={arguments.get('fail_to_pass')}, install_commands={arguments.get('install_commands')}"
            )
            return await self._handle_submit_tests(arguments, sandbox)

        else:
            return ToolResult(content=f"Unknown tool: {tool_name}", is_error=True)

    async def _handle_submit_tests(
        self, arguments: dict[str, Any], sandbox: SandboxProtocol
    ) -> ToolResult:
        """Handle submit_tests tool call."""
        fail_to_pass = arguments.get("fail_to_pass", [])
        pass_to_pass = arguments.get("pass_to_pass", [])
        test_files_raw = arguments.get("test_files", [])
        install_commands = arguments.get("install_commands", [])

        _validation_retry_count_var.set(_validation_retry_count_var.get() + 1)

        # Pre-apply validation: tests must FAIL on base commit
        valid, error = await self._validate_pre_apply(fail_to_pass, sandbox)
        if not valid:
            hint = _get_progressive_hint("PASSED on base", _validation_retry_count_var.get())
            return ToolResult(
                content=f"PRE-APPLY VALIDATION FAILED: {error}\n\n{hint}",
                is_error=True,
            )

        # Post-apply validation: tests must PASS after patch
        task = _task_var.get()
        if task and hasattr(task, "patch") and task.patch:
            valid, error = await self._validate_post_apply(
                fail_to_pass, task.patch, sandbox
            )
            if not valid:
                hint = _get_progressive_hint(
                    "FAILED after patch", _validation_retry_count_var.get()
                )
                return ToolResult(
                    content=f"POST-APPLY VALIDATION FAILED: {error}\n\n{hint}",
                    is_error=True,
                )

        # Parse test files
        test_files: list[TestFile] = []
        for tf in test_files_raw:
            if isinstance(tf, dict) and "path" in tf and "content" in tf:
                test_files.append(TestFile(path=tf["path"], content=tf["content"]))

        # Combine with written files
        all_files = list(_written_files_var.get())
        for tf in test_files:
            if not any(f.path == tf.path for f in all_files):
                all_files.append(tf)

        submit_result = SubmitResult(
            fail_to_pass=fail_to_pass,
            pass_to_pass=pass_to_pass,
            test_files=all_files,
            install_commands=install_commands,
        )

        return ToolResult(
            content="Tests submitted for validation.",
            submit_result=submit_result,
        )

    async def generate_tests(
        self,
        task: SweTask,
        sandbox: SandboxProtocol,
    ) -> GeneratedTests:
        """Generate test commands for a SWE task.

        Runs an agentic loop where the LLM explores the repository,
        writes tests, and validates them.

        Args:
            task: The SWE task to generate tests for.
            sandbox: Sandbox for executing commands.

        Returns:
            GeneratedTests with the generated test commands.

        Raises:
            RuntimeError: If the turn limit is exhausted without successful generation.
        """
        loop = AgenticLoop(
            max_turns=self._max_turns,
            max_context_tokens=self._max_context_tokens,
        )
        _written_files_var.set([])
        _task_var.set(task)
        _validation_retry_count_var.set(0)
        _dataset_prompt_var.set("")  # Reset for each async task
        validation_retries = 0

        tools = self._get_tools()

        loop.add_system(SYSTEM_PROMPT)

        user_msg = self._build_user_message(task)
        loop.add_user(user_msg)

        while not loop.is_exhausted():
            # Update preserved context before each LLM call
            preserved = []
            current_task = _task_var.get()
            if current_task and current_task.patch:
                preserved.append("Patch file available at: /workspace/forge/patch.diff")
            written_files = _written_files_var.get()
            if written_files:
                for wf in written_files:
                    preserved.append(f"Written file: {wf.path}")
            loop.set_preserved_context("\n".join(preserved))

            await loop.compact_if_needed(self._llm, self._model)

            request = GenerationRequest(
                model=self._model,
                messages=loop.messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                tools=tools,
                tool_choice="auto",
            )

            try:
                response = await self._llm.complete(request)
                loop.increment_turn()  # Count each LLM call as a turn
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                break

            if not response.choices:
                break

            choice = response.choices[0]
            message = choice.message

            # Handle tool calls
            if message.tool_calls:
                loop.add_assistant_with_tool_calls(message.content, message.tool_calls)

                for tc in message.tool_calls:
                    result = await self._handle_tool_call(tc, sandbox)

                    if result.submit_result:
                        # Check validation
                        validation_error = self._validate_submission(
                            result.submit_result, validation_retries
                        )

                        if validation_error:
                            validation_retries += 1
                            if validation_retries < MAX_VALIDATION_RETRIES:
                                loop.add_tool_result(
                                    tc.id, f"REJECTED: {validation_error}"
                                )
                                continue
                            else:
                                # Max retries, return what we have
                                return self._create_result(
                                    result.submit_result, loop.turn_count, success=False
                                )

                        # Success!
                        return self._create_result(
                            result.submit_result,
                            loop.turn_count,
                            success=True,
                        )
                    else:
                        loop.add_tool_result(tc.id, result.content)

                continue

            # No tool calls - FORCE TOOL USAGE
            # Agent must use tools, not write text
            loop.add_assistant(message.content or "")
            loop.add_user(
                "You must use tools to proceed. Based on your progress so far, "
                "call shell() to run a command, read_file() to examine code, "
                "write_file() to create a test, or submit_tests() if you're ready to submit. "
                "What is your next concrete action?"
            )
            continue

        # Exhausted turns without success
        return GeneratedTests(
            turn_count=loop.turn_count,
            dataset_prompt=_dataset_prompt_var.get(),
            success=False,
        )

    def _validate_submission(
        self,
        submit: SubmitResult,
        retry_count: int,
    ) -> str | None:
        """Validate a test submission.

        Returns None if valid, or an error message if invalid.
        """
        # Check fail_to_pass - ALWAYS required
        if not submit.fail_to_pass:
            return (
                "fail_to_pass must contain at least one test command. "
                "Write a test that FAILS on the base commit and PASSES "
                "after the PR patch is applied."
            )

        # Check install_commands - required for most languages
        # Go and Rust handle deps via their build tools, so allow empty
        task = _task_var.get()
        lang = (task.language if task else "").lower()
        needs_install = lang not in ("go", "golang", "rust")
        if needs_install and not submit.install_commands:
            return (
                "install_commands must contain at least one command. "
                "Run installation commands via shell first, verify they succeed "
                "(exit code 0), then include them in install_commands."
            )

        # Check for string-matching tests
        rejection = reject_string_matching_tests(submit.test_files)
        if rejection:
            return (
                f"{rejection}\n\n"
                "Rewrite your tests to check RUNTIME BEHAVIOR, not file contents. "
                "Import modules, call functions, check return values. "
                "Do NOT use open()/readFileSync() to read source and assert strings."
            )

        # Check test script validity
        script_issues = validate_test_scripts(submit.test_files)
        if script_issues:
            return f"{script_issues}\n\nFix the issues and resubmit."

        return None

    def _create_result(
        self,
        submit: SubmitResult,
        turn_count: int,
        success: bool,
    ) -> GeneratedTests:
        """Create GeneratedTests from a submit result."""
        return GeneratedTests(
            fail_to_pass=submit.fail_to_pass,
            pass_to_pass=submit.pass_to_pass,
            test_files=submit.test_files,
            install_commands=submit.install_commands,
            dataset_prompt=_dataset_prompt_var.get(),
            turn_count=turn_count,
            success=success,
        )
