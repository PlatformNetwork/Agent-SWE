"""Unified pipeline: mine + verify + build + push in one command.

This command runs the COMPLETE pipeline with automatic repair:
1. Generate tests via LLM agent (with validation retry)
2. Build Docker image
3. Verify FAIL→PASS (with repair loop up to 5x)
4. Push to Docker Hub and HuggingFace

NO HUMAN INTERVENTION - everything is autonomous.
"""

from __future__ import annotations

import asyncio
import base64
import tempfile
from logging import getLogger
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()
logger = getLogger(__name__)


def unified(
    repo: Annotated[str, typer.Option("--repo", "-r", help="Repository (owner/repo)")] = "",
    pr: Annotated[int, typer.Option("--pr", "-p", help="PR number")] = 0,
    output_dir: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory")
    ] = Path("./tasks"),
    docker_user: Annotated[
        Optional[str],
        typer.Option("--docker-user", "-d", help="Docker Hub username"),
    ] = None,
    hf_dataset: Annotated[
        str,
        typer.Option("--hf-dataset", "-h", help="HuggingFace dataset"),
    ] = "cortexlm/swe-forge",
    model: Annotated[
        str, typer.Option("--model", "-m", help="LLM model for test generation")
    ] = "moonshotai/kimi-k2.5:nitro",
    repair_model: Annotated[
        str, typer.Option("--repair-model", help="LLM model for repair")
    ] = "openai/gpt-4o-mini",
    max_repair_attempts: Annotated[
        int, typer.Option("--max-repair", help="Max repair attempts")
    ] = 5,
    push: Annotated[
        bool, typer.Option("--push", help="Push to Docker Hub and HuggingFace")
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", "-l", help="Max tasks from GH Archive"),
    ] = None,
) -> None:
    """Run unified pipeline: mine → verify → repair → build → push.
    
    Everything is autonomous with automatic repair loops.
    NO human intervention required.
    
    Examples:
        # Single PR
        swe-forge unified --repo python/cpython --pr 132391 --docker-user platformnetwork --push
        
        # Mine from GH Archive
        swe-forge unified --limit 10 --docker-user platformnetwork --push
        
        # Dry run (no push)
        swe-forge unified --repo django/django --pr 19171 --docker-user platformnetwork
    """
    import os
    
    # Check credentials
    github_token = os.environ.get("GITHUB_TOKEN")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    hf_token = os.environ.get("HF_TOKEN")
    
    if not github_token:
        console.print("[red]Error: GITHUB_TOKEN not set[/red]")
        raise typer.Exit(code=1)
    if not openrouter_key:
        console.print("[red]Error: OPENROUTER_API_KEY not set[/red]")
        raise typer.Exit(code=1)
    
    from swe_forge.execution.docker_client import DockerClient
    from swe_forge.swe.github_api import GitHubClient
    from swe_forge.llm.openrouter import OpenRouterClient
    from swe_forge.pipeline.complete_pipeline import CompleteMiningPipeline
    from swe_forge.publish.docker_builder import (
        build_docker_image,
        verify_with_repair,
        VerifyWithRepairResult,
    )
    from swe_forge.export.workspace import export_task_to_workspace
    from swe_forge.swe.models import SweTask
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async def run_unified():
        docker_client = DockerClient()
        gh_client = GitHubClient(github_token)
        llm_client = OpenRouterClient(openrouter_key)
        
        results = []
        
        try:
            async with docker_client:
                if repo and pr:
                    tasks = [await _process_single_pr(
                        gh_client, llm_client, docker_client,
                        repo, pr, model, output_dir, max_repair_attempts,
                        repair_model, docker_user, push
                    )]
                    results.extend(tasks)
                elif limit:
                    tasks = await _mine_from_archive(
                        gh_client, llm_client, docker_client,
                        limit, model, output_dir, max_repair_attempts,
                        repair_model, docker_user, push
                    )
                    results.extend(tasks)
                else:
                    console.print("[red]Error: Specify --repo and --pr, or --limit[/red]")
                    raise typer.Exit(code=1)
        finally:
            pass
        
        return results
    
    results = asyncio.run(run_unified())
    
    _display_results(results, push)
    
    if push and hf_token:
        _upload_to_huggingface(output_dir, hf_dataset, hf_token)


async def _process_single_pr(
    gh_client, llm_client, docker_client,
    repo: str, pr: int, model: str, output_dir: Path,
    max_repair: int, repair_model: str, docker_user: str | None, push: bool
) -> dict:
    """Process a single PR through the full pipeline."""
    console.print(f"\n[bold cyan]Processing {repo}#{pr}[/bold cyan]")
    
    from swe_forge.pipeline.complete_pipeline import CompleteMiningPipeline
    from swe_forge.publish.docker_builder import build_docker_image, verify_with_repair
    
    # Step 1: Mine and generate tests
    console.print("[yellow]Step 1: Mining and generating tests...[/yellow]")
    
    pipeline = CompleteMiningPipeline(
        gh_client=gh_client,
        llm_client=llm_client,
        docker_client=docker_client,
        model=model,
    )
    
    validated = await pipeline.run(repo, pr)
    
    if not validated:
        console.print(f"[red]✗ Failed to generate valid tests for {repo}#{pr}[/red]")
        return {"task_id": f"{repo.replace('/', '-')}-{pr}", "status": "failed", "stage": "generation"}
    
    task = validated.task
    task_id = task.id
    console.print(f"[green]✓ Tests generated and validated (FAIL→PASS)[/green]")
    
    # Step 2: Export workspace
    console.print("[yellow]Step 2: Exporting workspace...[/yellow]")
    task_dir = output_dir / task_id
    export_task_to_workspace(task, output_dir, docker_user)
    console.print(f"[green]✓ Exported to {task_dir}[/green]")
    
    # Step 3: Build Docker image
    if not docker_user:
        console.print("[yellow]Skipping Docker build (no --docker-user)[/yellow]")
        return {"task_id": task_id, "status": "success", "stage": "export"}
    
    console.print("[yellow]Step 3: Building Docker image...[/yellow]")
    
    try:
        image_name = await build_docker_image(task_dir, docker_user, push=push)
        console.print(f"[green]✓ Built image: {image_name}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Docker build failed: {e}[/red]")
        return {"task_id": task_id, "status": "failed", "stage": "docker_build", "error": str(e)}
    
    # Step 4: Verify with repair loop
    console.print(f"[yellow]Step 4: Verifying in Docker (max {max_repair} repairs)...[/yellow]")
    
    workspace_yaml = task_dir / "workspace.yaml"
    import yaml
    with open(workspace_yaml) as f:
        workspace = yaml.safe_load(f)
    
    result = await verify_with_repair(
        image_name=image_name,
        workspace=workspace,
        llm_client=llm_client,
        max_retries=max_repair,
        model=repair_model,
    )
    
    if result.success:
        repairs = len(result.repair_attempts)
        if repairs > 0:
            console.print(f"[green]✓ Verified after {repairs} repair(s)[/green]")
        else:
            console.print(f"[green]✓ Verified (no repairs needed)[/green]")
        
        if push:
            console.print(f"[green]✓ Pushed to Docker Hub: {image_name}[/green]")
        
        return {
            "task_id": task_id,
            "status": "success",
            "stage": "complete",
            "image": image_name,
            "repairs": len(result.repair_attempts)
        }
    else:
        console.print(f"[red]✗ Failed after {len(result.repair_attempts)} repair(s)[/red]")
        return {
            "task_id": task_id,
            "status": "failed",
            "stage": "verification",
            "repairs": len(result.repair_attempts),
            "error": result.final_error
        }


async def _mine_from_archive(
    gh_client, llm_client, docker_client,
    limit: int, model: str, output_dir: Path,
    max_repair: int, repair_model: str, docker_user: str | None, push: bool
) -> list[dict]:
    """Mine tasks from GH Archive."""
    console.print(f"\n[bold cyan]Mining {limit} tasks from GH Archive...[/bold cyan]")
    
    # This would integrate with the existing mining pipeline
    # For now, just process the first valid PR found
    console.print("[yellow]GH Archive mining not yet implemented[/yellow]")
    console.print("[yellow]Use --repo and --pr for specific tasks[/yellow]")
    return []


def _display_results(results: list[dict], push: bool):
    """Display results in a table."""
    table = Table(title="Pipeline Results")
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Stage")
    table.add_column("Repairs")
    if push:
        table.add_column("Pushed")
    
    for r in results:
        status_color = "green" if r["status"] == "success" else "red"
        repairs = str(r.get("repairs", 0))
        row = [
            r["task_id"],
            f"[{status_color}]{r['status']}[/{status_color}]",
            r.get("stage", "unknown"),
            repairs,
        ]
        if push:
            row.append("✓" if r["status"] == "success" and r.get("stage") == "complete" else "✗")
        table.add_row(*row)
    
    console.print(table)


def _upload_to_huggingface(output_dir: Path, dataset: str, token: str):
    """Upload tasks to HuggingFace."""
    console.print(f"\n[yellow]Uploading to HuggingFace: {dataset}[/yellow]")
    
    try:
        from datasets import Dataset
        import json
        
        tasks = []
        for task_dir in output_dir.iterdir():
            if task_dir.is_dir() and (task_dir / "workspace.yaml").exists():
                workspace_file = task_dir / "workspace.yaml"
                import yaml
                with open(workspace_file) as f:
                    workspace = yaml.safe_load(f)
                tasks.append(workspace)
        
        if tasks:
            ds = Dataset.from_list(tasks)
            ds.push_to_hub(dataset, token=token)
            console.print(f"[green]✓ Uploaded {len(tasks)} tasks to {dataset}[/green]")
    except Exception as e:
        console.print(f"[red]✗ HuggingFace upload failed: {e}[/red]")


# Register as a command
app = typer.Typer()
app.command(name="unified")(unified)
