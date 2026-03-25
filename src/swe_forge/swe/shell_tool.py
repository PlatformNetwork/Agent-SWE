"""Shell tool for executing commands in Docker sandbox with security controls.

This module provides the ShellTool class for safely executing commands
inside Docker containers with timeout enforcement and privilege blocking.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swe_forge.execution.sandbox import DockerSandbox

logger = getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30000
MAX_STDOUT_SIZE = 3000
MAX_STDERR_SIZE = 1500


@dataclass
class ShellResult:
    """Result of executing a shell command in a container.

    Attributes:
        stdout: Standard output from the command (truncated to MAX_STDOUT_SIZE).
        stderr: Standard error from the command (truncated to MAX_STDERR_SIZE).
        exit_code: Exit code of the command (0 for success).
        duration_ms: Execution duration in milliseconds.
        timed_out: Whether the command timed out.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False


class SecurityError(Exception):
    """Raised when a command is blocked for security reasons."""

    pass


BLOCKED_PATTERNS = [
    r"^sudo\s+",
    r"^su\s",
    r"\brm\s+-rf\s+/(?!\w)",
    r"\brm\s+-rf\s+$",
    r"\bdd\s+.*of=/dev/",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[06]",
    r"\bsystemctl\s+(stop|disable|mask)\s+",
    r"\biptables\b",
    r"\bip\s+.*route\s+del\b",
    r"\bifconfig\s+.*down\b",
    r"\buserdel\b",
    r"\busermod\b",
    r"\bpasswd\b",
    r"\bapt-get\s+(remove|purge|autoremove)\b",
    r"\bdpkg\s+--(remove|purge)\b",
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
    r"\bfork\s+bomb\b",
    r"\bdocker\s+(exec|run|attach)\b",
    r"\bnsenter\b",
    r"\bctr\b.*task\b",
    r"\bmodprobe\b",
    r"\binsmod\b",
    r"\brmmod\b",
    r"\bchmod\s+\+s\b",
    r"\bchmod\s+u\+s\b",
    r"\bchmod\s+g\+s\b",
]


def _is_command_blocked(command: str) -> tuple[bool, str | None]:
    """Check if a command matches any blocked pattern.

    Args:
        command: The command to check.

    Returns:
        Tuple of (is_blocked, reason). If blocked, reason contains the matched pattern.
    """
    normalized_cmd = command.strip()

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, normalized_cmd, re.IGNORECASE):
            return True, pattern

    return False, None


def _truncate_output(text: str, max_size: int) -> str:
    """Truncate output to max size.

    Args:
        text: Text to truncate.
        max_size: Maximum size in characters.

    Returns:
        Truncated text with "..." appended if truncated.
    """
    if len(text) <= max_size:
        return text
    return text[:max_size] + "..."


class ShellTool:
    """Tool for executing shell commands in a Docker sandbox.

    This class provides a safe interface for running commands inside
    Docker containers with:
    - Timeout enforcement
    - Privilege escalation blocking
    - Output truncation
    - Working directory isolation

    Usage:
        async with DockerSandbox(client) as sandbox:
            tool = ShellTool()
            result = await tool.execute(sandbox, "ls -la")
            print(result.stdout)
    """

    def __init__(
        self,
        *,
        max_stdout_size: int = MAX_STDOUT_SIZE,
        max_stderr_size: int = MAX_STDERR_SIZE,
        enable_security: bool = True,
    ) -> None:
        """Initialize ShellTool.

        Args:
            max_stdout_size: Maximum stdout size before truncation.
            max_stderr_size: Maximum stderr size before truncation.
            enable_security: Whether to enable security filtering (default: True).
        """
        self.max_stdout_size = max_stdout_size
        self.max_stderr_size = max_stderr_size
        self.enable_security = enable_security

    async def execute(
        self,
        container: "DockerSandbox",
        command: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ShellResult:
        """Execute a shell command in the Docker sandbox.

        Args:
            container: DockerSandbox instance to execute command in.
            command: Shell command to execute.
            timeout_ms: Timeout in milliseconds (default: 30000).
            cwd: Working directory override (defaults to sandbox workspace).
            env: Environment variables for the command.

        Returns:
            ShellResult with stdout, stderr, exit_code, duration_ms, timed_out.

        Raises:
            SecurityError: If command is blocked by security rules.
        """
        start_time = time.monotonic()

        if self.enable_security:
            is_blocked, pattern = _is_command_blocked(command)
            if is_blocked:
                logger.warning(
                    f"Blocked command matching pattern '{pattern}': {command[:100]}"
                )
                raise SecurityError(
                    f"Command blocked for security reasons (pattern: {pattern})"
                )

        timeout_seconds = timeout_ms / 1000.0

        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            result = await container.run_command(
                command,
                timeout=timeout_seconds,
                cwd=cwd,
                env=env,
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.exit_code

        except TimeoutError:
            timed_out = True
            exit_code = 124
            logger.warning(f"Command timed out after {timeout_ms}ms: {command[:100]}")

        duration_ms = int((time.monotonic() - start_time) * 1000)

        truncated_stdout = _truncate_output(stdout, self.max_stdout_size)
        truncated_stderr = _truncate_output(stderr, self.max_stderr_size)

        logger.debug(
            f"Shell executed: exit_code={exit_code}, duration={duration_ms}ms, "
            f"stdout_len={len(truncated_stdout)}, stderr_len={len(truncated_stderr)}, "
            f"timed_out={timed_out}"
        )

        return ShellResult(
            stdout=truncated_stdout,
            stderr=truncated_stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

    async def execute_unsafe(
        self,
        container: "DockerSandbox",
        command: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ShellResult:
        """Execute command bypassing security checks.

        WARNING: This method bypasses all security filtering. Use with extreme caution.

        Args:
            container: DockerSandbox instance to execute command in.
            command: Shell command to execute.
            timeout_ms: Timeout in milliseconds (default: 30000).
            cwd: Working directory override.
            env: Environment variables for the command.

        Returns:
            ShellResult with stdout, stderr, exit_code, duration_ms, timed_out.
        """
        start_time = time.monotonic()
        timeout_seconds = timeout_ms / 1000.0

        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            result = await container.run_command(
                command,
                timeout=timeout_seconds,
                cwd=cwd,
                env=env,
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.exit_code
        except TimeoutError:
            timed_out = True
            exit_code = 124

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return ShellResult(
            stdout=_truncate_output(stdout, self.max_stdout_size),
            stderr=_truncate_output(stderr, self.max_stderr_size),
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )


def validate_command(command: str) -> bool:
    """Validate that a command is safe to execute.

    Args:
        command: Command to validate.

    Returns:
        True if command is safe, False if blocked.
    """
    is_blocked, _ = _is_command_blocked(command)
    return not is_blocked
