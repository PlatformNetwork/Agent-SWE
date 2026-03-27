"""CI/CD file parser - extracts commands from config files.

This parser reads CI/CD configuration files and extracts the actual commands
that are run in CI. These commands are TESTED in CI, making them the most
reliable source for what works.

Supported formats:
- GitHub Actions (.github/workflows/*.yml)
- GitLab CI (.gitlab-ci.yml)
- Dockerfile
- Makefile
- CircleCI (.circleci/config.yml)
- Azure Pipelines (azure-pipelines.yml)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CICommands:
    """Commands extracted from CI/CD configuration files."""

    install_commands: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    build_commands: list[str] = field(default_factory=list)
    lint_commands: list[str] = field(default_factory=list)

    source_files: list[str] = field(default_factory=list)


def parse_github_actions(content: str) -> CICommands:
    """Parse GitHub Actions workflow file and extract commands."""
    result = CICommands()

    run_pattern = r'run:\s*\|?\s*["\']?([^"\n\']+)'
    for match in re.finditer(run_pattern, content):
        cmd = match.group(1).strip()
        categorize_command(cmd, result)

    return result


def parse_gitlab_ci(content: str) -> CICommands:
    """Parse GitLab CI configuration file and extract commands."""
    result = CICommands()

    script_pattern = r"script:\s*\n((?:\s+-+\s*.+\n)+)"
    for match in re.finditer(script_pattern, content):
        scripts = match.group(1)
        for line in scripts.split("\n"):
            cmd_match = re.search(r'-\s*["\']?([^"\n\'"]+)["\']?', line)
            if cmd_match:
                cmd = cmd_match.group(1).strip()
                categorize_command(cmd, result)

    return result


def parse_dockerfile(content: str) -> CICommands:
    """Parse Dockerfile and extract RUN commands."""
    result = CICommands()

    run_pattern = r"RUN\s+(.+?)(?:\n|$)"
    for match in re.finditer(run_pattern, content, re.IGNORECASE):
        cmd = match.group(1).strip()
        categorize_command(cmd, result)

    return result


def parse_makefile(content: str) -> CICommands:
    """Parse Makefile and extract target names."""
    result = CICommands()

    targets = re.findall(r"^([a-zA-Z_-]+):\s*$", content, re.MULTILINE)
    for target in targets:
        cmd = f"make {target}"
        categorize_command(cmd, result)

    return result


def categorize_command(cmd: str, result: CICommands) -> None:
    """Categorize a command into the appropriate list based on keywords."""
    cmd_lower = cmd.lower()

    install_keywords = [
        "install",
        "pip install",
        "npm install",
        "yarn",
        "cargo build",
        "go mod",
        "mvn install",
        "gradle",
    ]
    test_keywords = [
        "test",
        "pytest",
        "jest",
        "cargo test",
        "go test",
        "mvn test",
        "unittest",
    ]
    build_keywords = ["build", "compile", "webpack", "tsc", "cargo build", "go build"]
    lint_keywords = ["lint", "flake8", "eslint", "pylint", "black", "ruff", "mypy"]

    if any(kw in cmd_lower for kw in install_keywords):
        result.install_commands.append(cmd)
    elif any(kw in cmd_lower for kw in test_keywords):
        result.test_commands.append(cmd)
    elif any(kw in cmd_lower for kw in build_keywords):
        result.build_commands.append(cmd)
    elif any(kw in cmd_lower for kw in lint_keywords):
        result.lint_commands.append(cmd)
