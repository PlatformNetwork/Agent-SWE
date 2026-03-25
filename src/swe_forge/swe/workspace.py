"""Workspace configuration generator for SWE-bench datasets.

Generates complete workspace.yml files with:
- Environment setup (Python version, package manager)
- Install commands (apt-get, pip, poetry, etc.)
- Test commands (fail_to_pass, pass_to_pass)
- Repository configuration
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

import yaml


class PackageManager(str, Enum):
    """Package manager type."""
    PIP = "pip"
    POETRY = "poetry"
    UV = "uv"
    PIPENV = "pipenv"
    CONDA = "conda"
    SETUPTOOLS = "setuptools"


class PythonVersion(str, Enum):
    """Python version."""
    PY38 = "3.8"
    PY39 = "3.9"
    PY310 = "3.10"
    PY311 = "3.11"
    PY312 = "3.12"


@dataclass
class InstallConfig:
    """Installation configuration for a workspace."""
    
    python_version: PythonVersion = PythonVersion.PY312
    package_manager: PackageManager = PackageManager.PIP
    system_packages: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    pre_test_commands: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "python_version": self.python_version.value,
            "package_manager": self.package_manager.value,
            "system_packages": self.system_packages,
            "pip_packages": self.pip_packages,
            "install_commands": self.install_commands,
            "pre_test_commands": self.pre_test_commands,
        }


@dataclass
class WorkspaceConfig:
    """Complete workspace configuration for a SWE task."""
    
    task_id: str
    repo: str
    base_commit: str
    merge_commit: str
    install_config: InstallConfig
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    timeout_seconds: int = 600
    
    def to_yaml(self) -> str:
        """Generate workspace.yml content."""
        data = {
            "task_id": self.task_id,
            "repo": {
                "url": f"https://github.com/{self.repo}.git",
                "base_commit": self.base_commit,
                "merge_commit": self.merge_commit,
            },
            "environment": {
                "python_version": self.install_config.python_version.value,
                "package_manager": self.install_config.package_manager.value,
                "image": "ubuntu:22.04",
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
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    def save(self, path: str) -> None:
        """Save workspace.yml to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())


def detect_python_version(content: str) -> PythonVersion:
    """Detect Python version from pyproject.toml or setup.py content."""
    # Check pyproject.toml patterns
    if "requires-python" in content:
        match = re.search(r'requires-python\s*=\s*"[><=]*(\d+\.\d+)', content)
        if match:
            version = match.group(1)
            # Map to available versions
            if version.startswith("3.8"):
                return PythonVersion.PY38
            elif version.startswith("3.9"):
                return PythonVersion.PY39
            elif version.startswith("3.10"):
                return PythonVersion.PY310
            elif version.startswith("3.11"):
                return PythonVersion.PY311
    
    # Default to 3.11 for compatibility
    return PythonVersion.PY311


def detect_package_manager(files: dict[str, str]) -> PackageManager:
    """Detect package manager from repository files.
    
    Args:
        files: Dict mapping filename to content (e.g., {"pyproject.toml": "...", "setup.py": "..."})
    """
    if "pyproject.toml" in files:
        content = files["pyproject.toml"]
        if "[tool.poetry]" in content:
            return PackageManager.POETRY
        if "[tool.uv]" in content or "uv " in content:
            return PackageManager.UV
    
    if "Pipfile" in files:
        return PackageManager.PIPENV
    
    if "environment.yml" in files:
        return PackageManager.CONDA
    
    if "setup.py" in files:
        return PackageManager.SETUPTOOLS
    
    return PackageManager.PIP


def detect_system_dependencies(files: dict[str, str]) -> list[str]:
    """Detect system-level dependencies from repository files."""
    deps = ["git", "curl"]  # Always needed
    
    content = files.get("pyproject.toml", "") + files.get("setup.py", "") + files.get("requirements.txt", "")
    
    # Detect common system dependencies
    if "psycopg2" in content or "postgres" in content:
        deps.extend(["libpq-dev", "gcc"])
    
    if "Pillow" in content or "PIL" in content:
        deps.extend(["libjpeg-dev", "zlib1g-dev"])
    
    if "lxml" in content:
        deps.append("libxml2-dev")
    
    if "cryptography" in content:
        deps.extend(["libssl-dev", "libffi-dev"])
    
    if "pycurl" in content:
        deps.extend(["libcurl4-openssl-dev"])
    
    return list(set(deps))


def generate_install_commands(
    package_manager: PackageManager,
    system_packages: list[str],
    pip_packages: list[str],
) -> list[str]:
    """Generate install commands for the workspace.

    DEPRECATED: NO HARDCODED COMMANDS.
    
    The agent must discover the actual install commands by:
    1. Reading pyproject.toml, setup.py, package.json, etc.
    2. TRYING commands and tracking which succeed (exit 0)
    3. Using agentic_config.detect_repository_config()
    
    This function returns EMPTY LIST as fallback.
    Agent will populate via tools.
    """
    # NO HARDCODED COMMANDS - agent must discover everything
    # Use agentic_config for real detection
    return []  # Empty, agent will discover via tools


def create_workspace_config(
    task_id: str,
    repo: str,
    base_commit: str,
    merge_commit: str,
    fail_to_pass: list[str],
    pass_to_pass: list[str],
    files: dict[str, str] | None = None,
    pip_packages: list[str] | None = None,
    test_files: list[str] | None = None,
    timeout_seconds: int = 600,
) -> WorkspaceConfig:
    """Create a complete workspace configuration.
    
    Args:
        task_id: Unique task identifier
        repo: Repository in owner/repo format
        base_commit: Base commit SHA
        merge_commit: Merge commit SHA
        fail_to_pass: Tests that should fail on base, pass after patch
        pass_to_pass: Tests that should pass on both commits
        files: Repository files content for auto-detection
        pip_packages: Additional pip packages to install
        test_files: Test files created by agent
        timeout_seconds: Test execution timeout
    """
    files = files or {}
    pip_packages = pip_packages or []
    test_files = test_files or []
    
    # Auto-detect configuration
    pyproject_content = files.get("pyproject.toml", "")
    python_version = detect_python_version(pyproject_content)
    package_manager = detect_package_manager(files)
    system_packages = detect_system_dependencies(files)
    
    # Add common packages if pytest is mentioned
    if any("pytest" in cmd for cmd in fail_to_pass + pass_to_pass):
        if "pytest" not in pip_packages:
            pip_packages.append("pytest")
        if "pytest-asyncio" not in pip_packages:
            pip_packages.append("pytest-asyncio")
    
    # Generate install commands
    install_commands = generate_install_commands(package_manager, system_packages, pip_packages)
    
    # Create install config
    install_config = InstallConfig(
        python_version=python_version,
        package_manager=package_manager,
        system_packages=system_packages,
        pip_packages=pip_packages,
        install_commands=install_commands,
    )
    
    return WorkspaceConfig(
        task_id=task_id,
        repo=repo,
        base_commit=base_commit,
        merge_commit=merge_commit,
        install_config=install_config,
        fail_to_pass=fail_to_pass,
        pass_to_pass=pass_to_pass,
        test_files=test_files,
        timeout_seconds=timeout_seconds,
    )
