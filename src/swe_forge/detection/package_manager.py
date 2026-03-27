"""Package manager detection from file patterns.

Detection is RULE-BASED - this is OK to hardcode.
Commands are AGENTIC - NOT OK to hardcode.
"""

from __future__ import annotations

from enum import Enum


class PackageManager(str, Enum):
    """All supported package managers.

    Detection is based on FILE PATTERNS (rule-based).
    Commands are discovered by AGENT (not hardcoded).
    """

    # Python
    PIP = "pip"
    POETRY = "poetry"
    UV = "uv"
    PIPENV = "pipenv"

    # Node.js
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    BUN = "bun"

    # Rust
    CARGO = "cargo"

    # Go
    GO_MOD = "go-mod"

    # Ruby
    BUNDLER = "bundler"

    # PHP
    COMPOSER = "composer"

    # Java
    MAVEN = "maven"
    GRADLE = "gradle"

    # .NET
    NUGET = "nuget"

    # Dart/Flutter
    PUB = "pub"

    # Swift
    SPM = "swift-package-manager"
    COCOAPODS = "cocoapods"

    # Unknown
    UNKNOWN = "unknown"


PACKAGE_MANAGER_FILE_PATTERNS: dict[PackageManager, list[str]] = {
    PackageManager.PIP: ["requirements.txt", "setup.py", "setup.cfg"],
    PackageManager.POETRY: ["pyproject.toml", "poetry.lock"],
    PackageManager.UV: ["uv.lock"],
    PackageManager.PIPENV: ["Pipfile", "Pipfile.lock"],
    PackageManager.NPM: ["package.json", "package-lock.json"],
    PackageManager.YARN: ["yarn.lock"],
    PackageManager.PNPM: ["pnpm-lock.yaml"],
    PackageManager.BUN: ["bun.lockb", "bun.lock"],
    PackageManager.CARGO: ["Cargo.toml", "Cargo.lock"],
    PackageManager.GO_MOD: ["go.mod", "go.sum"],
    PackageManager.BUNDLER: ["Gemfile", "Gemfile.lock"],
    PackageManager.COMPOSER: ["composer.json", "composer.lock"],
    PackageManager.MAVEN: ["pom.xml"],
    PackageManager.GRADLE: ["build.gradle", "build.gradle.kts"],
    PackageManager.NUGET: ["*.csproj", "*.sln", "nuget.config"],
    PackageManager.PUB: ["pubspec.yaml", "pubspec.lock"],
    PackageManager.SPM: ["Package.swift"],
    PackageManager.COCOAPODS: ["Podfile", "Podfile.lock"],
}


def detect_package_manager(filenames: list[str]) -> PackageManager:
    """Detect package manager from file patterns.

    Args:
        filenames: List of filenames to check.

    Returns:
        Detected PackageManager, or PackageManager.UNKNOWN if not detected.
    """
    for filename in filenames:
        for pm, patterns in PACKAGE_MANAGER_FILE_PATTERNS.items():
            for pattern in patterns:
                if filename == pattern or filename.endswith(pattern.lstrip("*")):
                    return pm
    return PackageManager.UNKNOWN
