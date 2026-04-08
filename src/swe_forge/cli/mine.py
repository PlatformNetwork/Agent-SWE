"""Mine command for SWE task extraction.

Usage:
    swe-forge mine --repo owner/repo --limit 5 --output ./tasks.jsonl
    swe-forge mine --difficulty easy --model gpt-4 --once
    swe-forge mine --continuous
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Optional

from dotenv import load_dotenv

load_dotenv()

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

from swe_forge.llm.openrouter import OpenRouterClient
from swe_forge.swe.github_api import GitHubClient
from swe_forge.swe.gharchive import GhArchiveClient
from swe_forge.swe.models import SweTask
from swe_forge.swe.pipeline import (
    DifficultyTargets,
    SwePipeline,
    SwePipelineConfig,
    SwePipelineEventType,
)
from swe_forge.swe.test_generator import TestGenerator
from swe_forge.swe.concurrency import set_docker_containers_limit

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
    target: Annotated[
        int,
        typer.Option(
            "--target",
            "-t",
            help="Target number of VALID tasks to mine (stops when reached)",
            
        ),
    ] = 10,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="DEPRECATED: Use --target instead. Maximum number of tasks to mine",
            
        ),
    ] = 0,
    max_hours: Annotated[
        int,
        typer.Option(
            "--max-hours",
            help="Maximum hours to look back in GH Archive (default: 168 = 7 days)",
        ),
    ] = 168,
    min_complexity: Annotated[
        float,
        typer.Option(
            "--min-complexity",
            help="Minimum complexity score to accept tasks (default: 0.25)",
        ),
    ] = 0.25,
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
    ] = "moonshotai/kimi-k2.5:nitro",
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
            help="DEPRECATED: No longer used in target-based mining",
        ),
    ] = 0,
    min_stars: Annotated[
        int,
        typer.Option(
            "--min-stars",
            help="Minimum repository stars required",
        ),
    ] = 100,
    language: Annotated[
        Optional[str],
        typer.Option(
            "--language",
            help="Filter by programming language",
        ),
    ] = None,
    filter_json: Annotated[
        str,
        typer.Option(
            "--filter",
            "-f",
            help='JSON filter for max tasks per difficulty. Default: {"easy": 10, "medium": 10, "hard": 10}',
        ),
    ] = '{"easy": 10, "medium": 10, "hard": 10}',
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging",
        ),
    ] = False,
    parallel: Annotated[
        int,
        typer.Option(
            "--parallel",
            "-p",
            help="Maximum concurrent Docker containers",
            
        ),
    ] = 8,
    output_folder: Annotated[
        Path,
        typer.Option(
            "--output-folder",
            "-O",
            help="Output folder for workspace format export (REQUIRED)",
        ),
    ] = Path("./tasks"),
    docker_username: Annotated[
        str | None,
        typer.Option(
            "--docker-username",
            "-D",
            help="Docker Hub username for image names (user -> user/swe-forge-tasks:task-id)",
        ),
    ] = None,
    build_docker: Annotated[
        bool,
        typer.Option(
            "--build-docker",
            "-B",
            help="Build Docker images with repo + deps pre-installed for faster evaluation",
        ),
    ] = False,
    docker_push: Annotated[
        bool,
        typer.Option(
            "--docker-push",
            help="Push built Docker images to registry",
        ),
    ] = False,
    skip_duplicates: Annotated[
        bool,
        typer.Option(
            "--skip-duplicates",
            help="Skip tasks that have already been processed (checks local cache and optional HF dataset)",
        ),
    ] = False,
    hf_dataset: Annotated[
        Optional[str],
        typer.Option(
            "--hf-dataset",
            help="HuggingFace dataset ID to check for existing tasks (e.g., 'CortexLM/swe-forge')",
        ),
    ] = None,
    cache_dir: Annotated[
        Optional[str],
        typer.Option(
            "--cache-dir",
            help="Directory for dedup cache files (default: ./cache)",
        ),
    ] = None,
) -> None:
    """Mine SWE tasks from GitHub repositories.

    Extracts potential SWE-bench tasks from merged PRs using the pipeline.

    Examples:
        swe-forge mine --repo owner/repo --limit 5 --output ./tasks.jsonl
        swe-forge mine --difficulty easy --model gpt-4 --once
        swe-forge mine --continuous --limit 100
        swe-forge mine --limit 5 --build-docker --docker-username myuser
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    set_docker_containers_limit(parallel)

    if repo and not validate_repo_format(repo):
        console.print("[red]Error: Repository must be in 'owner/repo' format[/red]")
        raise typer.Exit(code=1)

    valid_difficulties = {"easy", "medium", "hard"}
    if difficulty and difficulty.lower() not in valid_difficulties:
        console.print(
            f"[red]Error: Difficulty must be one of: {', '.join(valid_difficulties)}[/red]"
        )
        raise typer.Exit(code=1)

    if continuous:
        once = False

    if build_docker and not docker_username:
        console.print(
            "[red]Error: --docker-username is required when using --build-docker[/red]"
        )
        raise typer.Exit(code=1)

    if limit > 0:
        console.print(
            "[yellow]Warning: --limit is deprecated. Use --target instead. "
            f"Using --target {limit}[/yellow]"
        )
        target = limit

    output_folder.mkdir(parents=True, exist_ok=True)

    languages = (
        [language.lower()]
        if language
        else ["python", "rust"]
    )
    difficulty_filter = difficulty.lower() if difficulty else None

    try:
        filter_config = json.loads(filter_json)
    except json.JSONDecodeError:
        console.print("[red]Error: Invalid JSON in --filter option[/red]")
        raise typer.Exit(code=1)

    difficulty_targets = DifficultyTargets(targets=filter_config)

    config = SwePipelineConfig(
        target_valid_tasks=target,
        max_hours_back=max_hours,
        batch_size_hours=6,
        min_complexity=min_complexity,
        max_candidates=max_candidates if max_candidates > 0 else 50,
        max_tasks=target,
        once=once,
        min_stars=min_stars,
        languages=languages,
        difficulty_filter=difficulty_filter,
        difficulty_targets=difficulty_targets,
    )

    github_token = os.environ.get("GITHUB_TOKEN", "")
    oxylabs_user = os.environ.get("OXYLABS_USERNAME", "")
    oxylabs_pass = os.environ.get("OXYLABS_PASSWORD", "")
    oxylabs_rps = int(os.environ.get("OXYLABS_RPS", "40"))

    console.print("[bold blue]SWE-Forge Mine Configuration[/bold blue]")
    console.print(f"  Repository: {repo or 'All repositories (from GH Archive)'}")
    console.print(f"  Target: {target} valid tasks")
    console.print(f"  Max Hours: {max_hours} hours back")
    console.print(f"  Min Complexity: {min_complexity}")
    console.print(f"  Output: {output}")
    console.print(f"  Difficulty: {difficulty or 'All'}")
    console.print(f"  Model: {model}")
    console.print(f"  Mode: {'Continuous' if continuous else 'Once'}")
    console.print(f"  Min Stars: {min_stars}")
    console.print(f"  Language: {language or 'python'}")
    console.print(f"  Filter: {filter_json}")
    console.print(f"  Parallel: {parallel} containers")
    if build_docker:
        console.print(f"  Build Docker: Yes (username: {docker_username})")
        console.print(f"  Push Images: {'Yes' if docker_push else 'No'}")
    if skip_duplicates:
        console.print(f"  Skip Duplicates: Yes")
        if hf_dataset:
            console.print(f"  HF Dataset: {hf_dataset}")
    if oxylabs_user:
        console.print(f"  Oxylabs Proxy: Enabled ({oxylabs_rps} req/s)")
    console.print()

    # Run the pipeline
    try:
        result = asyncio.run(
            _run_pipeline(
                github_token,
                config,
                repo,
                verbose,
                model,
                skip_duplicates=skip_duplicates,
                hf_dataset=hf_dataset,
                cache_dir=cache_dir,
                oxylabs_username=oxylabs_user,
                oxylabs_password=oxylabs_pass,
                oxylabs_rps=oxylabs_rps,
                output_folder=output_folder,
                docker_username=docker_username,
                build_docker=build_docker,
                docker_push=docker_push,
            )
        )

        if result.tasks:
            console.print(
                f"\n[green]{len(result.tasks)} tasks exported to {output_folder}[/green]"
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


async def _build_docker_images(
    tasks: list[SweTask],
    docker_username: str,
    *,
    push: bool = False,
    parallel: int = 2,
    verbose: bool = False,
):
    """Build Docker images for tasks with pre-installed dependencies."""
    from swe_forge.docker_test.image_builder import (
        build_images_for_tasks,
        task_to_dict,
    )
    from swe_forge.execution.docker_client import DockerClient

    task_dicts = [task_to_dict(t) for t in tasks]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        progress_task = progress.add_task("Building images...", total=len(tasks))

        async with DockerClient() as docker_client:
            results = await build_images_for_tasks(
                docker_client,
                task_dicts,
                docker_username,
                push=push,
                parallel=parallel,
            )

            for i, result in enumerate(results):
                status = "✅" if result.success else "❌"
                task_id = tasks[i].id
                if verbose or not result.success:
                    console.print(
                        f"  {status} {task_id}: {result.image_name or result.error}"
                    )
                progress.update(progress_task, advance=1)

    return results


def _update_workspace_docker(
    output_folder: Path, task_id: str, image_name: str
) -> None:
    """Update workspace.yaml with pre-built Docker image info."""
    import yaml

    workspace_path = output_folder / task_id / "workspace.yaml"
    if not workspace_path.exists():
        return

    with open(workspace_path, "r") as f:
        data = yaml.safe_load(f)

    # Update docker section to indicate pre-built image
    data["docker"] = {
        "image": image_name,
        "build": False,  # Already built
        "prebuilt": True,
    }

    with open(workspace_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


async def _build_and_verify_task(
    task_dir: Path,
    docker_username: str,
    *,
    push: bool = False,
    max_repair: int = 5,
    llm_client: "OpenRouterClient | None" = None,
    model: str = "moonshotai/kimi-k2.5:nitro",
) -> bool:
    """Build Docker image, verify with repair loop, optionally push.

    Returns True if image was successfully built and verified.
    """
    import yaml
    from swe_forge.publish.docker_builder import (
        build_docker_image,
        verify_with_repair,
        verify_docker_image,
    )

    workspace_path = task_dir / "workspace.yaml"
    if not workspace_path.exists():
        logger.warning(f"No workspace.yaml in {task_dir}")
        return False

    with open(workspace_path) as f:
        workspace = yaml.safe_load(f)

    task_id = task_dir.name
    result = await build_docker_image(task_dir, docker_username, push=False)
    if not result.success:
        logger.warning(f"Docker build failed for {task_id}: {result.error}")
        return False

    image_name = result.image_name
    logger.info(f"Built image {image_name}, verifying...")

    if llm_client:
        verify_result = await verify_with_repair(
            image_name=image_name,
            workspace=workspace,
            llm_client=llm_client,
            max_retries=max_repair,
            model=model,
        )
    else:
        vr = await verify_docker_image(image_name, workspace)
        from dataclasses import dataclass
        verify_result = type("R", (), {"success": vr.success, "repair_attempts": []})()

    if not verify_result.success:
        logger.warning(f"Docker verification failed for {task_id} after {len(verify_result.repair_attempts)} repairs")
        return False

    logger.info(f"Docker verified for {task_id} ({len(verify_result.repair_attempts)} repairs)")

    if push:
        import subprocess
        push_result = subprocess.run(
            ["docker", "push", image_name],
            capture_output=True, text=True, timeout=300,
        )
        if push_result.returncode != 0:
            logger.warning(f"Docker push failed for {task_id}: {push_result.stderr[:200]}")
            return False
        logger.info(f"Pushed {image_name}")

    return True


async def _run_pipeline(
    token: str,
    config: SwePipelineConfig,
    repo_filter: Optional[str],
    verbose: bool,
    model: str = "moonshotai/kimi-k2.5:nitro",
    *,
    skip_duplicates: bool = False,
    hf_dataset: Optional[str] = None,
    cache_dir: Optional[str] = None,
    oxylabs_username: str = "",
    oxylabs_password: str = "",
    oxylabs_rps: int = 40,
    output_folder: Path | None = None,
    docker_username: str | None = None,
    build_docker: bool = False,
    docker_push: bool = False,
):
    from dataclasses import dataclass, field
    from pathlib import Path

    @dataclass
    class PipelineResult:
        tasks: list = field(default_factory=list)
        benchmark_metrics: object = None

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    llm_client = None
    test_generator = None
    if openrouter_key:
        llm_client = OpenRouterClient(api_key=openrouter_key, default_model=model)
        test_generator = TestGenerator(llm=llm_client, model=model, max_turns=500)
        config.test_generator = test_generator
        config.concurrency_deep = 2

    if skip_duplicates:
        from swe_forge.swe.dedup import DedupManager, HuggingFaceDatasetCache
        from swe_forge.swe.pr_cache import PRCache

        cache_path = Path(cache_dir) if cache_dir else Path("./cache")
        cache_path.mkdir(parents=True, exist_ok=True)

        pr_cache = PRCache(cache_path)
        await pr_cache.open()

        hf_cache = None
        if hf_dataset:
            hf_cache = HuggingFaceDatasetCache(dataset_id=hf_dataset)
            await hf_cache.fetch_task_ids()

        config.dedup_manager = DedupManager(pr_cache=pr_cache, hf_cache=hf_cache)

    async with GitHubClient(
        token=token,
        oxylabs_username=oxylabs_username,
        oxylabs_password=oxylabs_password,
        oxylabs_rps=oxylabs_rps,
    ) as gh_client:
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
            progress_task = progress.add_task(
                "Mining tasks...", total=config.target_valid_tasks
            )

            async with SwePipeline(
                gh_client, gh_archive_client=gh_archive_client, config=config
            ) as pipeline:
                async for event in pipeline.run_with_progress():
                    if event.event_type == SwePipelineEventType.BATCH_FETCHED:
                        hours_start = event.data.get("hours_start", 0)
                        hours_end = event.data.get("hours_end", 0)
                        count = event.data.get("events_count", 0)
                        progress.update(
                            progress_task,
                            description=f"Fetched batch {hours_start}-{hours_end}h ({count} events)",
                        )

                    elif event.event_type == SwePipelineEventType.PIPELINE_PROGRESS:
                        valid_count = event.data.get("valid_count", 0)
                        target = event.data.get("target", config.target_valid_tasks)
                        progress.update(
                            progress_task,
                            completed=valid_count,
                            description=f"Mined {valid_count}/{target} valid tasks",
                        )

                    elif event.event_type == SwePipelineEventType.TASK_EXTRACTED:
                        task = event.data.get("task")
                        if task and isinstance(task, SweTask) and task.quality_passed:
                            tasks.append(task)
                            if output_folder:
                                from swe_forge.export.workspace import export_task_to_workspace
                                result_dir = export_task_to_workspace(
                                    task, output_folder,
                                    docker_username=docker_username,
                                    overwrite=True,
                                )
                                if result_dir:
                                    console.print(
                                        f"  [green]>> {task.id}[/green] exported to {result_dir}"
                                    )
                                    if build_docker and docker_username and llm_client:
                                        console.print(
                                            f"  [cyan]Agent setting up Docker for {task.id}...[/cyan]"
                                        )
                                        from swe_forge.agents.docker_setup_agent import DockerSetupAgent
                                        agent = DockerSetupAgent(llm_client, model=model, max_turns=100)
                                        image = await agent.setup_and_verify(
                                            result_dir,
                                            docker_username,
                                            push=docker_push,
                                        )
                                        if image:
                                            console.print(
                                                f"  [green]>> {task.id}[/green] Docker image ready: {image}"
                                                + (" (pushed)" if docker_push else "")
                                            )
                                        else:
                                            console.print(
                                                f"  [red]>> {task.id}[/red] Docker agent failed"
                                            )

                    elif event.event_type == SwePipelineEventType.PIPELINE_COMPLETED:
                        metrics = event.data.get("metrics")
                        target_reached = event.data.get("target_reached", False)
                        if target_reached:
                            progress.update(
                                progress_task,
                                completed=config.target_valid_tasks,
                                description=f"Target reached: {len(tasks)} tasks",
                            )
                        else:
                            progress.update(
                                progress_task,
                                description=f"Max hours reached: {len(tasks)} tasks",
                            )

        return PipelineResult(tasks=tasks, benchmark_metrics=metrics)


@app.command("complete")
def mine_complete(
    repo: Annotated[
        str,
        typer.Option(
            "--repo",
            "-r",
            help="Target repository in owner/repo format",
        ),
    ],
    pr: Annotated[
        int,
        typer.Option(
            "--pr",
            "-p",
            help="Pull request number to mine",
        ),
    ],
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for JSONL results",
        ),
    ] = "./tasks.jsonl",
    llm_model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="LLM model for test generation",
        ),
    ] = "moonshotai/kimi-k2.5:nitro",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging",
        ),
    ] = False,
    max_repair: Annotated[
        int,
        typer.Option(
            "--max-repair",
            help="Maximum automatic repair attempts (default: 5)",
        ),
    ] = 5,
    docker_user: Annotated[
        str | None,
        typer.Option(
            "--docker-user",
            "-d",
            help="Docker Hub username for build+push",
        ),
    ] = None,
    push: Annotated[
        bool,
        typer.Option(
            "--push",
            help="Push Docker image to registry",
        ),
    ] = False,
) -> None:
    """Complete A-Z mining with Docker verification and auto-repair.

    Runs the full pipeline with AUTOMATIC REPAIR:
    1. Fetch PR from GitHub
    2. Detect language
    3. Discover commands from CI/CD
    4. Generate tests via LLM
    5. Verify tests fail before patch (FAIL→PASS)
    6. If tests don't fail/pass correctly: AUTO-REPAIR (up to --max-repair times)
    7. Build Docker image (if --docker-user)
    8. Verify in Docker with repair loop
    9. Push to Docker Hub (if --push)
    10. Export validated task
    
    NO HUMAN INTERVENTION - everything is autonomous!
    
    Examples:
        # Full autonomous pipeline
        swe-forge mine complete --repo python/cpython --pr 132391 \
            --docker-user platformnetwork --push
        
        # With custom repair attempts
        swe-forge mine complete --repo django/django --pr 19171 --max-repair 10
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    github_token = os.environ.get("GITHUB_TOKEN", "")
    oxylabs_user = os.environ.get("OXYLABS_USERNAME", "")
    oxylabs_pass = os.environ.get("OXYLABS_PASSWORD", "")

    if not github_token and not (oxylabs_user and oxylabs_pass):
        console.print("[red]Error: Set GITHUB_TOKEN or OXYLABS_USERNAME/OXYLABS_PASSWORD[/red]")
        raise typer.Exit(code=1)

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

    console.print("[bold blue]Complete Mining Pipeline[/bold blue]")
    console.print(f"  Repository: {repo}")
    console.print(f"  PR: #{pr}")
    console.print(f"  Model: {llm_model}")
    console.print(f"  Output: {output}")
    if oxylabs_user:
        console.print(f"  Oxylabs Proxy: Enabled")
    console.print()

    try:
        result = asyncio.run(
            _run_complete_mining(
                repo, pr, output, llm_model, github_token, openrouter_key,
                max_repair=max_repair, docker_user=docker_user, push=push,
                oxylabs_username=oxylabs_user, oxylabs_password=oxylabs_pass,
            )
        )

        if result:
            console.print(f"\n[green]✅ Task validated: {result.task.id}[/green]")
            console.print(
                f"   Tests before: {'FAILED' if not result.before_tests_passed else 'PASSED'}"
            )
            console.print(
                f"   Tests after: {'PASSED' if result.after_tests_passed else 'FAILED'}"
            )
            console.print(f"   Exported to: {output}")
        else:
            console.print("\n[red]❌ Task failed verification[/red]")
            raise typer.Exit(code=1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Mining interrupted by user[/yellow]")
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


async def _run_complete_mining(
    repo: str,
    pr_number: int,
    output: str,
    model: str,
    github_token: str,
    openrouter_key: str,
    *,
    max_repair: int = 5,
    docker_user: str | None = None,
    push: bool = False,
    oxylabs_username: str = "",
    oxylabs_password: str = "",
):
    """Run the complete mining pipeline with automatic repair."""
    from swe_forge.pipeline import CompleteMiningPipeline
    from swe_forge.publish.docker_builder import build_docker_image, verify_with_repair
    from pathlib import Path
    import yaml

    llm_client = None
    if openrouter_key:
        llm_client = OpenRouterClient(api_key=openrouter_key, default_model=model)

    async with GitHubClient(
        token=github_token,
        oxylabs_username=oxylabs_username,
        oxylabs_password=oxylabs_password,
    ) as gh:
        pipeline = CompleteMiningPipeline(
            gh_client=gh,
            llm_client=llm_client,
            model=model,
        )

        # Step 1: Mine and verify with repair loop
        console.print("[cyan]Step 1: Mining and test generation (with auto-repair)...[/cyan]")
        result = await pipeline.mine_pr(repo, pr_number, max_repair_attempts=max_repair)

        if not result:
            console.print("[red]Failed after repair attempts[/red]")
            return None

        # Step 2: Export workspace
        console.print("[cyan]Step 2: Exporting workspace...[/cyan]")
        output_dir = Path(output).parent if Path(output).suffix else Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        from swe_forge.export.workspace import export_task_to_workspace
        task_dir = export_task_to_workspace(result.task, output_dir, docker_user)
        console.print(f"[green]Exported to: {task_dir}[/green]")

        # Step 3: Build Docker image (if requested)
        if docker_user:
            console.print("[cyan]Step 3: Building Docker image...[/cyan]")
            try:
                image_name = await build_docker_image(task_dir, docker_user, push=False)
                console.print(f"[green]Built image: {image_name}[/green]")
                
                # Step 4: Verify in Docker with repair loop
                console.print(f"[cyan]Step 4: Verifying in Docker (max {max_repair} repairs)...[/cyan]")
                
                workspace_file = task_dir / "workspace.yaml"
                with open(workspace_file) as f:
                    workspace = yaml.safe_load(f)
                
                verify_result = await verify_with_repair(
                    image_name=image_name,
                    workspace=workspace,
                    llm_client=llm_client,
                    max_retries=max_repair,
                    model=model,
                )
                
                if verify_result.success:
                    repairs = len(verify_result.repair_attempts)
                    console.print(f"[green]Verified in Docker ({repairs} repairs)[/green]")
                    
                    # Step 5: Push if requested
                    if push:
                        console.print("[cyan]Step 5: Pushing to Docker Hub...[/cyan]")
                        import subprocess
                        push_result = subprocess.run(
                            ["docker", "push", image_name],
                            capture_output=True,
                            text=True,
                        )
                        if push_result.returncode == 0:
                            console.print(f"[green]Pushed: {image_name}[/green]")
                        else:
                            console.print(f"[red]Push failed: {push_result.stderr}[/red]")
                else:
                    console.print(f"[red]Docker verification failed after {len(verify_result.repair_attempts)} repairs[/red]")
                    return None
                    
            except Exception as e:
                console.print(f"[red]Docker build/verify failed: {e}[/red]")
                logger.error(f"Docker error: {e}")

        return result


if __name__ == "__main__":
    app()
