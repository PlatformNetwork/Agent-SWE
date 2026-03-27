"""Language enum and detection from file patterns.

Detection is RULE-BASED - this is OK to hardcode.
Commands are AGENTIC - NOT OK to hardcode.
"""

from __future__ import annotations

import fnmatch
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Language(str, Enum):
    """All supported programming languages.

    Detection is based on FILE PATTERNS (rule-based).
    Commands are discovered by AGENT (not hardcoded).
    """

    # Dynamic/Scripting
    PYTHON = "python"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    PHP = "php"
    PERL = "perl"
    LUA = "lua"
    R = "r"
    JULIA = "julia"

    # Systems/Compiled
    RUST = "rust"
    GO = "go"
    C = "c"
    CPP = "cpp"
    ZIG = "zig"
    ODIN = "odin"
    NIM = "nim"
    V = "v"
    CRYSTAL = "crystal"

    # JVM
    JAVA = "java"
    KOTLIN = "kotlin"
    SCALA = "scala"
    CLOJURE = "clojure"

    # BEAM
    ELIXIR = "elixir"
    ERLANG = "erlang"

    # Functional
    HASKELL = "haskell"
    OCAML = "ocaml"
    FSHARP = "fsharp"

    # .NET
    DOTNET = "dotnet"

    # Mobile
    SWIFT = "swift"
    DART = "dart"
    FLUTTER = "flutter"
    KOTLIN_ANDROID = "kotlin-android"

    # Web/Frontend
    ELM = "elm"
    PURESCRIPT = "purescript"

    # Data/Config
    MARKDOWN = "markdown"
    YAML = "yaml"
    JSON = "json"

    # Unknown
    UNKNOWN = "unknown"


# File patterns for each language (RULE-BASED - OK to hardcode)
LANGUAGE_FILE_PATTERNS: dict[Language, list[str]] = {
    # Python
    Language.PYTHON: [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
        "*.py",
        "py/python",
        "app.py",
        "main.py",
        "__init__.py",
    ],
    # Node.js
    Language.NODEJS: [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "bun.lock",
        ".npmrc",
        ".yarnrc",
        "*.js",
        "*.cjs",
        "*.mjs",
        "*.jsx",
    ],
    # TypeScript
    Language.TYPESCRIPT: [
        "tsconfig.json",
        "tsconfig.*.json",
        "tslint.json",
        "*.ts",
        "*.tsx",
        "*.mts",
        "*.cts",
    ],
    # Ruby
    Language.RUBY: [
        "Gemfile",
        "Gemfile.lock",
        "Rakefile",
        "*.gemspec",
        "*.rb",
        "*.rake",
        "config.ru",
    ],
    # PHP
    Language.PHP: [
        "composer.json",
        "composer.lock",
        "*.php",
        "*.phar",
        "phpcs.xml",
        "phpunit.xml",
    ],
    # Perl
    Language.PERL: [
        "cpanfile",
        "cpanfile.snapshot",
        "*.pl",
        "*.pm",
        "*.t",
    ],
    # Lua
    Language.LUA: [
        "*.lua",
        "*.rockspec",
        "luarocks",
    ],
    # R
    Language.R: [
        "DESCRIPTION",
        "*.R",
        "*.Rmd",
        "*.r",
        ".Rprofile",
    ],
    # Julia
    Language.JULIA: [
        "Project.toml",
        "Manifest.toml",
        "*.jl",
    ],
    # Rust
    Language.RUST: [
        "Cargo.toml",
        "Cargo.lock",
        "*.rs",
        "rust-toolchain.toml",
    ],
    # Go
    Language.GO: [
        "go.mod",
        "go.sum",
        "*.go",
        "go.work",
    ],
    # C
    Language.C: [
        "Makefile",
        "*.c",
        "*.h",
        "configure",
        "configure.ac",
        "CMakeLists.txt",
    ],
    # C++
    Language.CPP: [
        "*.cpp",
        "*.cc",
        "*.cxx",
        "*.hpp",
        "*.hxx",
        "*.hh",
        "CMakeLists.txt",
        "Meson.build",
    ],
    # Zig
    Language.ZIG: [
        "build.zig",
        "*.zig",
        "build.zig.zon",
    ],
    # Odin
    Language.ODIN: [
        "*.odin",
        "ols.json",
    ],
    # Nim
    Language.NIM: [
        "*.nim",
        "*.nimble",
        "nimble.lock",
    ],
    # V
    Language.V: [
        "*.v",
        "v.mod",
    ],
    # Crystal
    Language.CRYSTAL: [
        "shard.yml",
        "shard.lock",
        "*.cr",
    ],
    # Java
    Language.JAVA: [
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "*.java",
        "gradlew",
    ],
    # Kotlin
    Language.KOTLIN: [
        "*.kt",
        "*.kts",
        "*.ktm",
    ],
    # Scala
    Language.SCALA: [
        "build.sbt",
        "*.scala",
        "*.sc",
        "project/build.properties",
    ],
    # Clojure
    Language.CLOJURE: [
        "project.clj",
        "deps.edn",
        "*.clj",
        "*.cljs",
        "*.cljc",
    ],
    # Elixir
    Language.ELIXIR: [
        "mix.exs",
        "mix.lock",
        "*.ex",
        "*.exs",
    ],
    # Erlang
    Language.ERLANG: [
        "rebar.config",
        "*.erl",
        "*.hrl",
        "*.beam",
    ],
    # Haskell
    Language.HASKELL: [
        "stack.yaml",
        "cabal.project",
        "*.cabal",
        "*.hs",
        "hpack.yaml",
    ],
    # OCaml
    Language.OCAML: [
        "dune",
        "dune-project",
        "*.ml",
        "*.mli",
        "opam",
    ],
    # F#
    Language.FSHARP: [
        "*.fs",
        "*.fsi",
        "*.fsx",
    ],
    # .NET
    Language.DOTNET: [
        "*.csproj",
        "*.fsproj",
        "*.vbproj",
        "*.sln",
        "*.cs",
        "*.fs",
        "*.vb",
        "global.json",
        "nuget.config",
    ],
    # Swift
    Language.SWIFT: [
        "Package.swift",
        "*.swift",
        "Podfile",
        "Cartfile",
    ],
    # Dart
    Language.DART: [
        "pubspec.yaml",
        "pubspec.lock",
        "*.dart",
    ],
    # Flutter
    Language.FLUTTER: [
        "pubspec.yaml",
        "lib/main.dart",
        "android/",
        "ios/",
    ],
    # Elm
    Language.ELM: [
        "elm.json",
        "*.elm",
    ],
    # PureScript
    Language.PURESCRIPT: [
        "spago.dhall",
        "*.purs",
        "packages.dhall",
    ],
    # Markdown (documentation)
    Language.MARKDOWN: [
        "*.md",
        "*.markdown",
    ],
    # YAML (config)
    Language.YAML: [
        "*.yaml",
        "*.yml",
        # But exclude known language-specific files
        # (not *.yaml that matches other patterns)
    ],
    # JSON (config)
    Language.JSON: [
        "*.json",
    ],
}


def detect_language(files: dict[str, str]) -> Language:
    """Detect language from files content dict.

    Args:
        files: Dict mapping filename to file content.
               Use empty content if only checking existence.

    Returns:
        Detected Language, or Language.UNKNOWN if not detected.

    Example:
        >>> detect_language({"package.json": '{"name": "my-app"}'})
        <Language.NODEJS: 'nodejs'>
    """
    for filename in files.keys():
        language = _detect_language_from_filename(filename)
        if language != Language.UNKNOWN:
            return language
    return Language.UNKNOWN


def detect_language_from_files(filenames: list[str]) -> Language:
    """Detect language from list of filenames.

    Args:
        filenames: List of filenames to check.

    Returns:
        Detected Language, or Language.UNKNOWN if not detected.

    Example:
        >>> detect_language_from_files(["Cargo.toml", "src/main.rs"])
        <Language.RUST: 'rust'>
    """
    for filename in filenames:
        language = _detect_language_from_filename(filename)
        if language != Language.UNKNOWN:
            return language
    return Language.UNKNOWN


def _detect_language_from_filename(filename: str) -> Language:
    """Detect language from a single filename using patterns.

    Checks patterns in priority order (more specific first).
    """
    # Priority check: specific files before wildcards
    for language, patterns in LANGUAGE_FILE_PATTERNS.items():
        for pattern in patterns:
            # Check exact match first
            if filename == pattern:
                return language
            # Then check glob pattern
            if fnmatch.fnmatch(filename, pattern):
                return language
    return Language.UNKNOWN


def get_language_default_version(language: Language) -> str:
    """Get default version for a language.

    This is used when version cannot be detected from files.
    """
    DEFAULT_VERSIONS: dict[Language, str] = {
        Language.PYTHON: "3.11",
        Language.NODEJS: "20",
        Language.TYPESCRIPT: "5.3",
        Language.RUST: "1.75",
        Language.GO: "1.21",
        Language.JAVA: "17",
        Language.KOTLIN: "1.9",
        Language.SCALA: "2.13",
        Language.RUBY: "3.2",
        Language.PHP: "8.2",
        Language.SWIFT: "5.9",
        Language.DART: "3.0",
        Language.ELIXIR: "1.16",
        Language.ERLANG: "26",
        Language.HASKELL: "9.4",
        Language.DOTNET: "8.0",
    }
    return DEFAULT_VERSIONS.get(language, "unknown")
