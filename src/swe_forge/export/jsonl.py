"""JSONL export/import for SweTask objects."""

import json
from collections.abc import Iterator
from pathlib import Path

from swe_forge.swe.models import SweTask


def export_jsonl(tasks: list[SweTask], path: str | Path, append: bool = False) -> None:
    """Write SweTask objects to JSONL file (one JSON per line).

    Args:
        tasks: List of SweTask objects to export.
        path: Output file path.
        append: If True, append to existing file. If False, overwrite.
    """
    mode = "a" if append else "w"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open(mode, encoding="utf-8") as f:
        for task in tasks:
            f.write(task.model_dump_json() + "\n")


def import_jsonl(path: str | Path) -> list[SweTask]:
    """Read JSONL file and return list of SweTask objects.

    Args:
        path: Input file path.

    Returns:
        List of SweTask objects.

    Raises:
        ValueError: If a line contains invalid JSON or invalid SweTask data.
    """
    return list(stream_jsonl(path))


def stream_jsonl(path: str | Path) -> Iterator[SweTask]:
    """Generator for memory-efficient JSONL reading.

    Args:
        path: Input file path.

    Yields:
        SweTask objects one at a time.

    Raises:
        ValueError: If a line contains invalid JSON or invalid SweTask data.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                yield SweTask.model_validate(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e
            except Exception as e:
                raise ValueError(f"Invalid SweTask data at line {line_num}: {e}") from e
