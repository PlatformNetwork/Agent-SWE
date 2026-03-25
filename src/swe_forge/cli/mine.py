"""Mine command for SWE task extraction.

Usage:
    swe-forge mine --repo owner/repo --limit 5 --output ./tasks.jsonl
    swe-forge mine --difficulty easy --model gpt-4 --once
    swe-forge mine --continuous
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from swe_forge.export.jsonl import export_jsonl
from swe_forge.swe.github_api import GitHubClient
from swe_forge.swe.gharchive import GhArchiveClient
from swe_forge.swe.models import SweTask
from swe_forge.swe.pipeline import (
    DifficultyTargets,
    SwePipeline,
    SwePipelineConfig,
    SwePipelineEvent,
    SwePipelineEventType,
)

logger = logging.getLogger(__name__)

app = typer.Typer(name="mine", help="Mine SWE tasks from GitHub repositories")

console = Console()


def validate_repo_format(repo: str) -> bool:
    """Validate repository format is owner/repo."""
    if not repo:
        return False
    parts = repo.split("/")
    return len(parts) == 2 and all(p.strip() for p in parts)


@app.command()
def mine(
    repo: Annotated[
        Optional[str],
        typer.Option(
            "--repo",
            "-r",
            help="Target repository in owner/repo format",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of tasks to mine",
            min=1,
        ),
    ] = 10,
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for JSONL results",
        ),
    ] = "./tasks.jsonl",
    difficulty: Annotated[
        Optional[str],
        typer.Option(
            "--difficulty",
            "-d",
            help="Filter by difficulty level (easy/medium/hard)",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="LLM model for classification",
        ),
    ] = "gpt-4",
    once: Annotated[
        bool,
        typer.Option(
            "--once",
            help="Run once then exit",
        ),
    ] = True,
    continuous: Annotated[
        bool,
        typer.Option(
            "--continuous",
            help="Keep running continuously",
        ),
    ] = False,
    max_candidates: Annotated[
        int,
        typer.Option(
            "--max-candidates",
            help="Maximum PR candidates to process",
        ),
    ] = 50,
    min_stars: Annotated[
        int,
        typer.Option(
            "--min-stars",
            help="Minimum repository stars required",
        ),
    ] = 20,
    language: Annotated[
        Optional[str],
        typer.Option(
            "--language",
            help="Filter by programming language",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging",
        ),
    ] = False,
) -> None:
    """Mine SWE tasks from GitHub repositories.

    Extracts potential SWE-bench tasks from merged PRs using the pipeline.

    Examples:
        swe-forge mine --repo owner/repo --limit 5 --output ./tasks.jsonl
        swe-forge mine --difficulty easy --model gpt-4 --once
        swe-forge mine --continuous --limit 100
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Validate repo format if provided
    if repo and not validate_repo_format(repo):
        console.print("[red]Error: Repository must be in 'owner/repo' format[/red]")
        raise typer.Exit(code=1)

    # Validate difficulty
    valid_difficulties = {"easy", "medium", "hard"}
    if difficulty and difficulty.lower() not in valid_difficulties:
        console.print(
            f"[red]Error: Difficulty must be one of: {', '.join(valid_difficulties)}[/red]"
        )
        raise typer.Exit(code=1)

    # Handle once/continuous conflict
    if continuous:
        once = False

    # Validate output directory
    output_path = Path(output)
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build pipeline config
    languages = [language.lower()] if language else ["python"]
    difficulty_filter = difficulty.lower() if difficulty else None

    config = SwePipelineConfig(
        max_candidates=max_candidates,
        max_tasks=limit,
        once=once,
        min_stars=min_stars,
        languages=languages,
        difficulty_filter=difficulty_filter,
    )

    # Get GitHub token from environment
    github_token = os.environ.get("GITHUB_TOKEN", "")

    # Display configuration
    console.print("[bold blue]SWE-Forge Mine Configuration[/bold blue]")
    console.print(f"  Repository: {repo or 'All repositories (from GH Archive)'}")
    console.print(f"  Limit: {limit} tasks")
    console.print(f"  Output: {output}")
    console.print(f"  Difficulty: {difficulty or 'All'}")
    console.print(f"  Model: {model}")
    console.print(f"  Mode: {'Continuous' if continuous else 'Once'}")
    console.print(f"  Min Stars: {min_stars}")
    console.print(f"  Language: {language or 'python'}")
    console.print()

    # Run the pipeline
    try:
        result = asyncio.run(_run_pipeline(github_token, config, repo, verbose))

        if result.tasks:
            # Export results
            export_jsonl(result.tasks, output_path)
            console.print(
                f"\n[green]Exported {len(result.tasks)} tasks to {output}[/green]"
            )

            # Print summary
            if result.benchmark_metrics:
                metrics = result.benchmark_metrics
                console.print("\n[bold]Pipeline Summary:[/bold]")
                console.print(f"  Total candidates: {metrics.total_prefiltered}")
                console.print(f"  Enriched: {metrics.enriched_count}")
                console.print(f"  Filter passed: {metrics.filter_passed}")
                console.print(f"  Tasks extracted: {metrics.extraction_succeeded}")
                console.print(f"  Quality passed: {metrics.quality_passed}")
        else:
            console.print("\n[yellow]No tasks extracted[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Mining interrupted by user[/yellow]")
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


async def _run_pipeline(
    token: str,
    config: SwePipelineConfig,
    repo_filter: Optional[str],
    verbose: bool,
) -> "PipelineResult":
    """Run the SWE pipeline with progress tracking."""
    from dataclasses import dataclass, field

    @dataclass
    class PipelineResult:
        tasks: list = field(default_factory=list)
        benchmark_metrics: object = None

    gh_client = GitHubClient(token=token)
    gh_archive_client = GhArchiveClient(token=token) if not repo_filter else None

    tasks: list[SweTask] = []
    metrics = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Mining tasks...", total=config.max_tasks)

        async with SwePipeline(
            gh_client, gh_archive_client=gh_archive_client, config=config
        ) as pipeline:
            async for event in pipeline.run_with_progress():
                if event.event_type == SwePipelineEventType.TASK_EXTRACTED:
                    task = event.data.get("task")
                    if task and isinstance(task, SweTask):
                        tasks.append(task)
                        progress.update(
                            task_id, advance=1, description=f"Mined {len(tasks)} tasks"
                        )

                elif event.event_type == SwePipelineEventType.PIPELINE_COMPLETED:
                    metrics = event.data.get("metrics")
                    progress.update(task_id, completed=len(tasks))

    return PipelineResult(tasks=tasks, benchmark_metrics=metrics)


if __name__ == "__main__":
    app()
