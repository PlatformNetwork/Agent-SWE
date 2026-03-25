"""Patch extractor for separating solution and test changes.

This module extracts diffs from PR data, separating solution patches
from test patches based on file path patterns.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedPatch:
    """Result of extracting patches from a diff.

    Attributes:
        solution_patch: Non-test file changes
        test_patch: Test file changes only
        files_changed: Total number of files modified
        added_lines: Total lines added
        removed_lines: Total lines removed
        summary: Brief description of changes
    """

    solution_patch: str
    test_patch: str
    files_changed: int
    added_lines: int
    removed_lines: int
    summary: str


# Test file name patterns
_TEST_FILE_PATTERNS = [
    r"^test_.*\.py$",  # test_*.py
    r"^.*_test\.py$",  # *_test.py
    r"^.*_test\.rs$",  # *_test.rs
    r"^.*\.test\.ts$",  # *.test.ts
    r"^.*\.spec\.js$",  # *.spec.js
    r"^.*\.spec\.ts$",  # *.spec.ts
    r"^.*\.test\.js$",  # *.test.js
    r"^conftest\.py$",  # pytest conftest
    r"^pytest\.ini$",  # pytest config
    r"^jest\.config\.js$",  # jest config
    r"^jest\.config\.ts$",  # jest config ts
    r"^vitest\.config\.ts$",  # vitest config
    r"^setup\.cfg$",  # may contain test config
]

# Test directory patterns
_TEST_DIR_PATTERNS = [
    r"^tests?/",  # tests/ or test/ at root
    r"/tests?/",  # /tests/ or /test/ nested
    r"^__tests__/",  # __tests__/ at root
    r"/__tests__/",  # __tests__/ nested
    r"^spec/",  # spec/ at root
    r"/spec/",  # spec/ nested
]


def is_test_file(path: str) -> bool:
    """Check if a file path is a test file.

    Args:
        path: File path to check

    Returns:
        True if the file is a test file, False otherwise
    """
    normalized = path.replace("\\", "/")
    filename = normalized.split("/")[-1]

    for pattern in _TEST_FILE_PATTERNS:
        if re.match(pattern, filename):
            return True

    for pattern in _TEST_DIR_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


def parse_diff_file_name(line: str) -> Optional[str]:
    """Parse the file name from a diff header line.

    Parses lines like: 'diff --git a/path/to/file.py b/path/to/file.py'

    Args:
        line: A diff header line starting with 'diff --git'

    Returns:
        The file path, or None if the line is not a valid diff header
    """
    # Match 'diff --git a/path b/path' format
    match = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
    if match:
        return match.group(2)

    match = re.match(r"^diff --git a/(.+?) a/(.+)$", line)
    if match:
        return match.group(2)

    return None


def _split_into_blocks(raw: str) -> list[tuple[str, str]]:
    """Split a diff into blocks, each starting with 'diff --git'.

    Args:
        raw: The raw diff content

    Returns:
        List of tuples (file_path, block_content)
    """
    if not raw:
        return []

    blocks = []
    current_file = None
    current_lines: list[str] = []

    for line in raw.splitlines():
        if line.startswith("diff --git"):
            if current_file is not None and current_lines:
                blocks.append((current_file, "\n".join(current_lines) + "\n"))
            current_file = parse_diff_file_name(line)
            current_lines = [line] if current_file else []
        elif current_file is not None:
            current_lines.append(line)

    if current_file is not None and current_lines:
        blocks.append((current_file, "\n".join(current_lines) + "\n"))

    return blocks


def split_solution_and_tests(raw: str) -> tuple[str, str]:
    """Split a diff into solution and test patches.

    Args:
        raw: The raw diff content

    Returns:
        Tuple of (solution_patch, test_patch)
    """
    if not raw:
        return "", ""

    blocks = _split_into_blocks(raw)

    solution_blocks: list[str] = []
    test_blocks: list[str] = []

    for file_path, block_content in blocks:
        if is_test_file(file_path):
            test_blocks.append(block_content)
        else:
            solution_blocks.append(block_content)

    solution_patch = "".join(solution_blocks)
    test_patch = "".join(test_blocks)

    return solution_patch, test_patch


def count_line_delta(raw: str) -> tuple[int, int]:
    """Count added and removed lines in a diff.

    Args:
        raw: The raw diff content

    Returns:
        Tuple of (added_lines, removed_lines)
    """
    added = 0
    removed = 0

    for line in raw.splitlines():
        if line.startswith(("diff --git", "@@", "index ", "+++", "---")):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return added, removed


def extract_patch(raw: str, summary: str = "") -> ExtractedPatch:
    """Extract and split patches from raw diff content.

    Args:
        raw: The raw diff content
        summary: Optional description of the changes

    Returns:
        ExtractedPatch with separated solution and test patches
    """
    solution_patch, test_patch = split_solution_and_tests(raw)
    added, removed = count_line_delta(raw)
    blocks = _split_into_blocks(raw)

    return ExtractedPatch(
        solution_patch=solution_patch,
        test_patch=test_patch,
        files_changed=len(blocks),
        added_lines=added,
        removed_lines=removed,
        summary=summary,
    )
