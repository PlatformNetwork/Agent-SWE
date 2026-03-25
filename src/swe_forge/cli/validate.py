"""Validate command for SWE task validation.

Usage:
    swe-forge validate --input tasks.jsonl
    swe-forge validate --input tasks.jsonl --fix --output valid_tasks.jsonl
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from swe_forge.export.jsonl import export_jsonl
from swe_forge.swe.models import SweTask

logger = logging.getLogger(__name__)

app = typer.Typer(name="validate", help="Validate SWE tasks from JSONL files")

console = Console()


class TaskValidationResult:
    """Result of validating a single task."""

    def __init__(
        self, task_id: str, valid: bool, errors: list[str], fixed: bool = False
    ):
        self.task_id = task_id
        self.valid = valid
        self.errors = errors
        self.fixed = fixed


def validate_task_schema(data: dict) -> tuple[bool, list[str]]:
    """Validate task data against SweTask schema.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required field: id
    if "id" not in data or not data["id"]:
        errors.append("Missing required field: id")

    # Try Pydantic validation
    try:
        SweTask.model_validate(data)
    except ValidationError as e:
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append(f"Schema validation error in '{field}': {error['msg']}")

    return len(errors) == 0, errors


def validate_required_fields(data: dict) -> tuple[bool, list[str]]:
    """Validate that all required fields are present and non-empty.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    required_fields = ["id", "repo", "base_commit", "merge_commit"]

    for field in required_fields:
        if field not in data or not data.get(field):
            errors.append(f"Missing or empty required field: {field}")

    return len(errors) == 0, errors


def validate_patch_format(patch: str) -> tuple[bool, list[str]]:
    """Validate that patch is in valid unified diff format.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not patch:
        # Empty patch is acceptable (no changes needed)
        return True, []

    # Basic patch format validation
    if not patch.startswith("--- "):
        errors.append("Patch must start with '--- ' (unified diff format)")

    if "\n+++" not in patch and "+++" not in patch:
        errors.append("Patch must contain '+++' marker (unified diff format)")

    # Check for hunk markers
    if "@@" not in patch:
        errors.append("Patch must contain hunk markers '@@'")

    return len(errors) == 0, errors


def fix_task(data: dict) -> tuple[dict, list[str]]:
    """Attempt to fix common issues in task data.

    Returns:
        Tuple of (fixed_data, list_of_fixes_applied)
    """
    fixes = []
    fixed_data = data.copy()

    # Fix: Ensure id is string
    if "id" in fixed_data and not isinstance(fixed_data["id"], str):
        fixed_data["id"] = str(fixed_data["id"])
        fixes.append("Converted id to string")

    # Fix: Add default values for optional fields if missing
    defaults = {
        "language": "unknown",
        "difficulty_score": 1,
        "patch": "",
        "test_patch": "",
        "fail_to_pass": [],
        "pass_to_pass": [],
        "install_config": {},
        "meta": {},
        "prompt": "",
        "original_pr_body": "",
    }

    for field, default in defaults.items():
        if field not in fixed_data:
            fixed_data[field] = default
            fixes.append(f"Added default value for {field}")

    return fixed_data, fixes


def validate_jsonl_file(
    input_path: Path,
    fix: bool = False,
) -> tuple[list[dict], list[TaskValidationResult]]:
    """Validate all tasks in a JSONL file.

    Args:
        input_path: Path to input JSONL file
        fix: Whether to attempt fixing invalid tasks

    Returns:
        Tuple of (valid_tasks, validation_results)
    """
    valid_tasks: list[dict] = []
    results: list[TaskValidationResult] = []

    with input_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                result = TaskValidationResult(
                    task_id=f"line_{line_num}",
                    valid=False,
                    errors=[f"Invalid JSON: {e}"],
                )
                results.append(result)
                continue

            task_id = data.get("id", f"line_{line_num}")
            all_errors: list[str] = []

            # Schema validation
            schema_valid, schema_errors = validate_task_schema(data)
            all_errors.extend(schema_errors)

            # Required fields validation
            fields_valid, field_errors = validate_required_fields(data)
            all_errors.extend(field_errors)

            # Patch format validation
            patch = data.get("patch", "")
            patch_valid, patch_errors = validate_patch_format(patch)
            all_errors.extend(patch_errors)

            is_valid = schema_valid and fields_valid and patch_valid

            # Attempt fix if requested
            fixed = False
            if fix and not is_valid:
                fixed_data, fixes = fix_task(data)
                # Re-validate after fix
                schema_valid, schema_errors = validate_task_schema(fixed_data)
                fields_valid, field_errors = validate_required_fields(fixed_data)
                patch_valid, patch_errors = validate_patch_format(
                    fixed_data.get("patch", "")
                )

                if schema_valid and fields_valid and patch_valid:
                    data = fixed_data
                    is_valid = True
                    fixed = True

            result = TaskValidationResult(
                task_id=task_id,
                valid=is_valid,
                errors=all_errors if not is_valid else [],
                fixed=fixed,
            )
            results.append(result)

            if is_valid:
                valid_tasks.append(data)

    return valid_tasks, results


@app.command()
def validate(
    input: Annotated[
        str,
        typer.Option(
            "--input",
            "-i",
            help="Input JSONL file with tasks",
        ),
    ],
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            "-f",
            help="Attempt to fix invalid tasks",
        ),
    ] = False,
    output: Annotated[
        Optional[str],
        typer.Option(
            "--output",
            "-o",
            help="Output file for valid tasks",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """Validate SWE tasks from a JSONL file.

    Performs validation checks on each task including:
    - Schema validation against SweTask model
    - Required fields presence check
    - Patch format validation

    Examples:
        swe-forge validate --input tasks.jsonl
        swe-forge validate --input tasks.jsonl --fix --output valid_tasks.jsonl
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    input_path = Path(input)

    # Validate input file exists
    if not input_path.exists():
        console.print(f"[red]Error: Input file '{input}' not found[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Validating tasks from {input}[/bold blue]")
    console.print(f"  Fix mode: {'enabled' if fix else 'disabled'}")
    if output:
        console.print(f"  Output: {output}")
    console.print()

    # Run validation
    valid_tasks, results = validate_jsonl_file(input_path, fix=fix)

    # Display results summary
    total = len(results)
    passed = sum(1 for r in results if r.valid)
    failed = total - passed
    fixed_count = sum(1 for r in results if r.fixed)

    # Build summary table
    table = Table(title="Validation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")

    table.add_row("Total Tasks", str(total))
    table.add_row("Valid", str(passed), style="green")
    table.add_row("Invalid", str(failed), style="red" if failed > 0 else "green")
    if fix:
        table.add_row(
            "Fixed", str(fixed_count), style="yellow" if fixed_count > 0 else "green"
        )

    console.print(table)

    # Show detailed errors if verbose
    if verbose and failed > 0:
        console.print("\n[bold]Detailed Errors:[/bold]")
        for result in results:
            if not result.valid:
                console.print(f"\n[red]Task: {result.task_id}[/red]")
                for error in result.errors:
                    console.print(f"  - {error}")

    # Export valid tasks if output specified
    if output and valid_tasks:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_jsonl([SweTask.model_validate(t) for t in valid_tasks], output_path)
        console.print(
            f"\n[green]Exported {len(valid_tasks)} valid tasks to {output}[/green]"
        )

    # Exit with error code if validation failed
    if failed > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
