"""Export command for converting task formats.

Usage:
    swe-forge export --input tasks.jsonl --format parquet --output tasks.parquet
    swe-forge export --input tasks.jsonl --format jsonl --output tasks_copy.jsonl
    swe-forge export --input tasks.jsonl --format hf --repo my-org/my-dataset
"""

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from swe_forge.export.hf_upload import upload_to_hf
from swe_forge.export.jsonl import export_jsonl, import_jsonl
from swe_forge.export.parquet import export_parquet

logger = logging.getLogger(__name__)

app = typer.Typer(name="export", help="Export SWE tasks to various formats")

console = Console()


def validate_format(format: str) -> bool:
    """Validate format is one of the allowed values."""
    if format is None:
        return False
    return format in ("jsonl", "parquet", "hf")


@app.command()
def export(
    input: Annotated[
        str,
        typer.Option(
            "--input",
            "-i",
            help="Input JSONL file with tasks",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format (jsonl/parquet/hf)",
        ),
    ] = "parquet",
    output: Annotated[
        Optional[str],
        typer.Option(
            "--output",
            "-o",
            help="Output file path (for jsonl/parquet)",
        ),
    ] = None,
    repo: Annotated[
        Optional[str],
        typer.Option(
            "--repo",
            "-r",
            help="HuggingFace repository ID (for hf format, e.g., 'org/dataset-name')",
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
    """Export SWE tasks from JSONL to various formats.

    Converts tasks from JSONL format to the specified output format.

    Examples:
        swe-forge export --input tasks.jsonl --format parquet --output tasks.parquet
        swe-forge export --input tasks.jsonl --format jsonl --output tasks_copy.jsonl
        swe-forge export --input tasks.jsonl --format hf --repo my-org/my-dataset
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    input_path = Path(input)

    if not input_path.exists():
        console.print(f"[red]Error: Input file '{input}' not found[/red]")
        raise typer.Exit(code=1)

    if not validate_format(format):
        console.print(
            f"[red]Error: Invalid format '{format}'. Must be one of: jsonl, parquet, hf[/red]"
        )
        raise typer.Exit(code=1)

    if format == "hf":
        if not repo:
            console.print("[red]Error: --repo is required when format is 'hf'[/red]")
            raise typer.Exit(code=1)
    else:
        if not output:
            console.print(
                f"[red]Error: --output is required when format is '{format}'[/red]"
            )
            raise typer.Exit(code=1)

    console.print(f"[bold blue]Exporting tasks from {input}[/bold blue]")
    console.print(f"  Format: {format}")
    if output:
        console.print(f"  Output: {output}")
    if repo:
        console.print(f"  Repo: {repo}")
    console.print()

    try:
        console.print("[dim]Reading input file...[/dim]")
        tasks = import_jsonl(input_path)
        console.print(f"[green]Loaded {len(tasks)} tasks[/green]")
    except Exception as e:
        console.print(f"[red]Error reading input file: {e}[/red]")
        raise typer.Exit(code=1)

    if not tasks:
        console.print("[yellow]No tasks to export[/yellow]")
        return

    try:
        if format == "jsonl":
            output_path = Path(output)
            export_jsonl(tasks, output_path)
            console.print(f"\n[green]Exported {len(tasks)} tasks to {output}[/green]")

        elif format == "parquet":
            output_path = Path(output)
            count = export_parquet(tasks, output_path)
            console.print(f"\n[green]Exported {count} tasks to {output}[/green]")

        elif format == "hf":
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_path = Path(tmpdir) / "data.parquet"
                console.print("[dim]Creating parquet file...[/dim]")
                export_parquet(tasks, temp_path)
                console.print(f"[dim]Uploading to HuggingFace: {repo}[/dim]")
                upload_to_hf(temp_path, repo)
                console.print(
                    f"\n[green]Uploaded {len(tasks)} tasks to https://huggingface.co/datasets/{repo}[/green]"
                )

    except Exception as e:
        logger.error(f"Export error: {e}")
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
