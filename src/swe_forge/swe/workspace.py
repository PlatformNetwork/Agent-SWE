"""Workspace configuration generator for SWE-bench datasets.

Generates complete workspace.yml files with:
- Environment setup (language version, package manager)
- Install commands (discovered by agent, NOT hardcoded)
- Test commands (fail_to_pass, pass_to_pass)
- Repository configuration

IMPORTANT: Commands are AGENTIC - discovered by the agent at runtime.
Detection (language/PM) is RULE-BASED - OK to hardcode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from swe_forge.detection import Language, PackageManager
from swe_forge.detection.language import get_language_default_version


@dataclass
class InstallConfig:
    """Install configuration - AGENTIC, not hardcoded.

    Commands are EMPTY by default - the agent discovers them by:
    1. Reading pyproject.toml, setup.py, package.json, Cargo.toml, etc.
    2. TRYING commands and tracking which succeed (exit 0)
    3. Using agentic_config.detect_repository_config()

    This dataclass is a schema - not a command generator.
    """

    language: Language = Language.PYTHON
    package_manager: PackageManager = PackageManager.PIP
    language_version: str = "unknown"  # Detected from files

    # These are EMPTY by default - agent fills them
    system_packages: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    pre_test_commands: list[str] = field(default_factory=list)

    # Discovery metadata
    discovery_source: str = "none"  # none, ci-cd, llm, package-files
    discovery_confidence: str = "unknown"  # high, medium, low, unknown

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "language": self.language.value,
            "package_manager": self.package_manager.value,
            "language_version": self.language_version,
            "system_packages": self.system_packages,
            "pip_packages": self.pip_packages,
            "install_commands": self.install_commands,
            "pre_test_commands": self.pre_test_commands,
            "discovery": {
                "source": self.discovery_source,
                "confidence": self.discovery_confidence,
            },
        }


@dataclass
class WorkspaceConfig:
    """Complete workspace configuration for any SWE task.

    Language-agnostic - works for Python, Rust, Go, Node.js, etc.
    """

    task_id: str
    repo: str
    base_commit: str
    merge_commit: str

    # Language info
    language: Language
    install_config: InstallConfig

    # Tests
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)

    timeout_seconds: int = 600

    def to_yaml(self) -> str:
        """Generate workspace.yml content."""
        data = {
            "task_id": self.task_id,
            "language": self.language.value,
            "repo": {
                "url": f"https://github.com/{self.repo}.git",
                "base_commit": self.base_commit,
                "merge_commit": self.merge_commit,
            },
            "environment": {
                "language_version": self.install_config.language_version,
                "package_manager": self.install_config.package_manager.value,
                "image": "ubuntu:24.04",
            },
            "install": {
                "system_packages": self.install_config.system_packages,
                "pip_packages": self.install_config.pip_packages,
                "commands": self.install_config.install_commands,
            },
            "tests": {
                "fail_to_pass": self.fail_to_pass,
                "pass_to_pass": self.pass_to_pass,
                "test_files": self.test_files,
            },
            "execution": {
                "timeout_seconds": self.timeout_seconds,
                "pre_test_commands": self.install_config.pre_test_commands,
            },
        }
        return yaml.dump(
            data, default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    def save(self, path: str) -> None:
        """Save workspace.yml to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())


def create_workspace_config(
    task_id: str,
    repo: str,
    base_commit: str,
    merge_commit: str,
    fail_to_pass: list[str],
    pass_to_pass: list[str],
    files: dict[str, str] | None = None,
    test_files: list[str] | None = None,
    timeout_seconds: int = 600,
) -> WorkspaceConfig:
    """Create workspace configuration with AGENTIC discovery.

    Commands are NOT generated here - agent discovers them.
    We only detect language and package manager (rule-based, OK).

    Args:
        task_id: Unique task identifier
        repo: Repository in owner/repo format
        base_commit: Base commit SHA
        merge_commit: Merge commit SHA
        fail_to_pass: Tests that should fail on base, pass after patch
        pass_to_pass: Tests that should pass on both commits
        files: Repository files content for auto-detection (filename -> content)
        test_files: Test files created by agent
        timeout_seconds: Test execution timeout

    Returns:
        WorkspaceConfig with empty install commands (agent fills them)
    """
    from swe_forge.detection import detect_language, detect_package_manager

    files = files or {}
    test_files = test_files or []

    # Detect language and package manager (rule-based, OK)
    language = detect_language(files)
    filenames = list(files.keys())

    # detect_package_manager takes a list of filenames
    package_manager = detect_package_manager(filenames)
    language_version = get_language_default_version(language)

    # Commands are NOT generated here - agent discovers them
    # (empty by default, filled by AgenticCommandDiscovery)
    install_config = InstallConfig(
        language=language,
        package_manager=package_manager,
        language_version=language_version,
        system_packages=[],  # Agent discovers
        install_commands=[],  # Agent discovers
        discovery_source="none",  # Will be updated when agent discovers
        discovery_confidence="unknown",
    )

    return WorkspaceConfig(
        task_id=task_id,
        repo=repo,
        base_commit=base_commit,
        merge_commit=merge_commit,
        language=language,
        install_config=install_config,
        fail_to_pass=fail_to_pass,
        pass_to_pass=pass_to_pass,
        test_files=test_files,
        timeout_seconds=timeout_seconds,
    )
