#!/usr/bin/env python3
"""Revalidate all SWE-Forge tasks for quality.

This script runs:
1. Complexity evaluation (filter trivial tasks)
2. Docker verification (filter broken tests)

Usage:
    python scripts/revalidate_tasks.py --tasks-dir ./tasks --report report.json
    python scripts/revalidate_tasks.py --from-hf --min-complexity 0.25
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class RevalidationResult:
    """Result of revalidating a single task."""

    task_id: str
    complexity_score: float
    complexity_difficulty: str
    complexity_passed: bool
    verification_passed: bool
    verification_error: str | None = None
    action: str = "keep"  # "keep", "reject_complexity", "reject_verification"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RevalidationReport:
    """Full revalidation report."""

    total_tasks: int = 0
    kept: int = 0
    rejected_complexity: int = 0
    rejected_verification: int = 0
    results: list[RevalidationResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "kept": self.kept,
            "rejected_complexity": self.rejected_complexity,
            "rejected_verification": self.rejected_verification,
            "acceptance_rate": f"{self.kept / self.total_tasks * 100:.1f}%"
            if self.total_tasks > 0
            else "N/A",
            "results": [asdict(r) for r in self.results],
        }


def load_yaml(path: Path) -> dict:
    """Load YAML file."""
    import yaml

    with open(path) as f:
        return yaml.safe_load(f)


async def evaluate_complexity(
    patch: str, tests: list[str], prompt: str
) -> tuple[float, str, bool]:
    """Evaluate task complexity.

    Returns:
        (score, difficulty, should_accept)
    """
    from swe_forge.evaluators import ComplexityEvaluator

    evaluator = ComplexityEvaluator()
    verdict = evaluator.evaluate(patch, tests, prompt)
    accept, _ = evaluator.should_accept(verdict)

    return verdict.score, verdict.difficulty, accept


async def verify_task(
    task_id: str,
    image_name: str,
    workspace: dict,
    timeout: int = 180,
    repair: bool = False,
    llm_client=None,
    repair_model: str = "openai/gpt-4o-mini",
    max_retries: int = 5,
) -> tuple[bool, str | None]:
    """Verify task in Docker.

    Args:
        task_id: Task identifier
        image_name: Docker image name
        workspace: Workspace configuration
        timeout: Verification timeout
        repair: Whether to use repair mode
        llm_client: LLM client for repair mode
        repair_model: Model to use for repair
        max_retries: Max repair attempts

    Returns:
        (passed, error_message)
    """
    from swe_forge.publish.docker_builder import verify_docker_image, verify_with_repair

    try:
        if repair and llm_client:
            logger.info(
                f"[{task_id}] Running verification with repair (model={repair_model})..."
            )
            result = await verify_with_repair(
                image_name,
                workspace,
                llm_client,
                max_retries=max_retries,
                model=repair_model,
                timeout=timeout,
            )
            if result.repair_attempts:
                logger.info(
                    f"[{task_id}] Repair attempts: {len(result.repair_attempts)}"
                )
            return result.success, result.final_error or result.original_error
        else:
            result = await verify_docker_image(image_name, workspace, timeout=timeout)
            return result.success, result.error
    except Exception as e:
        return False, str(e)


async def revalidate_task(
    task_dir: Path,
    min_complexity: float = 0.25,
    run_verification: bool = True,
    verify_timeout: int = 180,
    repair: bool = False,
    llm_client=None,
    repair_model: str = "openai/gpt-4o-mini",
    max_retries: int = 5,
) -> RevalidationResult:
    task_id = task_dir.name
    workspace_path = task_dir / "workspace.yaml"
    patch_path = task_dir / "patch.diff"

    # Load workspace
    if not workspace_path.exists():
        return RevalidationResult(
            task_id=task_id,
            complexity_score=0.0,
            complexity_difficulty="",
            complexity_passed=False,
            verification_passed=False,
            verification_error="workspace.yaml not found",
            action="reject_verification",
        )

    workspace = load_yaml(workspace_path)
    patch = patch_path.read_text() if patch_path.exists() else ""
    tests = workspace.get("tests", {}).get("fail_to_pass", [])
    prompt = workspace.get("prompt", "")
    image_name = workspace.get("environment", {}).get(
        "image", f"platformnetwork/swe-forge:{task_id}"
    )

    # Step 1: Complexity evaluation
    logger.info(f"[{task_id}] Running complexity evaluation...")
    score, difficulty, complexity_accept = await evaluate_complexity(
        patch, tests, prompt
    )

    if not complexity_accept or score < min_complexity:
        return RevalidationResult(
            task_id=task_id,
            complexity_score=score,
            complexity_difficulty=difficulty,
            complexity_passed=False,
            verification_passed=False,
            action="reject_complexity",
            details={"reason": f"Score {score:.2f} below threshold {min_complexity}"},
        )

    # Step 2: Docker verification
    if run_verification:
        logger.info(f"[{task_id}] Running Docker verification...")
        verify_passed, verify_error = await verify_task(
            task_id,
            image_name,
            workspace,
            timeout=verify_timeout,
            repair=repair,
            llm_client=llm_client,
            repair_model=repair_model,
            max_retries=max_retries,
        )

        if not verify_passed:
            return RevalidationResult(
                task_id=task_id,
                complexity_score=score,
                complexity_difficulty=difficulty,
                complexity_passed=True,
                verification_passed=False,
                verification_error=verify_error,
                action="reject_verification",
            )
    else:
        verify_passed = True
        verify_error = None

    # All checks passed
    return RevalidationResult(
        task_id=task_id,
        complexity_score=score,
        complexity_difficulty=difficulty,
        complexity_passed=True,
        verification_passed=verify_passed,
        verification_error=verify_error,
        action="keep",
    )


async def revalidate_all(
    tasks_dir: Path,
    min_complexity: float = 0.25,
    run_verification: bool = True,
    verify_timeout: int = 180,
    limit: int | None = None,
    repair: bool = False,
    llm_client=None,
    repair_model: str = "openai/gpt-4o-mini",
    max_retries: int = 5,
) -> RevalidationReport:
    """Revalidate all tasks in directory.

    Args:
        tasks_dir: Directory containing task folders
        min_complexity: Minimum complexity score
        run_verification: Whether to run Docker verification
        verify_timeout: Timeout per verification
        limit: Maximum tasks to process

    Returns:
        RevalidationReport with all results
    """
    report = RevalidationReport()

    # Find all task directories
    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir()])
    if limit:
        task_dirs = task_dirs[:limit]

    report.total_tasks = len(task_dirs)

    for task_dir in task_dirs:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Processing: {task_dir.name}")
        logger.info(f"{'=' * 50}")

        result = await revalidate_task(
            task_dir,
            min_complexity=min_complexity,
            run_verification=run_verification,
            verify_timeout=verify_timeout,
            repair=repair,
            llm_client=llm_client,
            repair_model=repair_model,
            max_retries=max_retries,
        )

        report.results.append(result)

        if result.action == "keep":
            report.kept += 1
            logger.info(f"  ✅ KEEP: score={result.complexity_score:.2f}")
        elif result.action == "reject_complexity":
            report.rejected_complexity += 1
            logger.warning(
                f"  ❌ REJECT (complexity): score={result.complexity_score:.2f}"
            )
        elif result.action == "reject_verification":
            report.rejected_verification += 1
            logger.warning(f"  ❌ REJECT (verification): {result.verification_error}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Revalidate SWE-Forge tasks")
    parser.add_argument(
        "--tasks-dir", type=str, default="./tasks", help="Tasks directory"
    )
    parser.add_argument(
        "--from-hf", action="store_true", help="Load from HuggingFace instead"
    )
    parser.add_argument(
        "--hf-dataset", type=str, default="CortexLM/swe-forge", help="HF dataset name"
    )
    parser.add_argument(
        "--min-complexity", type=float, default=0.25, help="Minimum complexity score"
    )
    parser.add_argument(
        "--no-verification", action="store_true", help="Skip Docker verification"
    )
    parser.add_argument(
        "--verify-timeout", type=int, default=180, help="Verification timeout"
    )
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    parser.add_argument(
        "--report",
        type=str,
        default="revalidation_report.json",
        help="Output report file",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="Parallel tasks (careful with Docker)"
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Use repair mode with LLM agent to fix failing tests",
    )
    parser.add_argument(
        "--repair-model",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model for repair agent",
    )
    parser.add_argument(
        "--max-retries", type=int, default=5, help="Maximum repair attempts per task"
    )
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.error("Set OPENROUTER_API_KEY environment variable")
        sys.exit(1)

    tasks_dir = Path(args.tasks_dir)

    if args.from_hf:
        logger.info(f"Loading from HuggingFace: {args.hf_dataset}")
        logger.warning("HF loading not implemented yet, use --tasks-dir")
        sys.exit(1)

    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        sys.exit(1)

    logger.info(f"Revalidating tasks in: {tasks_dir}")
    logger.info(f"Min complexity: {args.min_complexity}")
    logger.info(f"Run verification: {not args.no_verification}")

    # Create LLM client if repair mode is enabled
    llm_client = None
    if args.repair:
        from swe_forge.llm.openrouter import OpenRouterClient

        llm_client = OpenRouterClient(api_key=os.environ["OPENROUTER_API_KEY"])
        logger.info(f"Repair mode enabled with model: {args.repair_model}")

    # Run revalidation
    report = asyncio.run(
        revalidate_all(
            tasks_dir,
            min_complexity=args.min_complexity,
            run_verification=not args.no_verification,
            verify_timeout=args.verify_timeout,
            limit=args.limit,
            repair=args.repair,
            llm_client=llm_client,
            repair_model=args.repair_model,
            max_retries=args.max_retries,
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("REVALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total tasks:     {report.total_tasks}")
    print(f"Kept:            {report.kept}")
    print(f"Rejected (complexity): {report.rejected_complexity}")
    print(f"Rejected (verification): {report.rejected_verification}")
    print(
        f"Acceptance rate: {report.kept / report.total_tasks * 100:.1f}%"
        if report.total_tasks > 0
        else "N/A"
    )
    print("=" * 60)

    # Save report
    with open(args.report, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info(f"Report saved to: {args.report}")

    # Print rejected tasks
    print("\n--- REJECTED TASKS ---")
    for r in report.results:
        if r.action != "keep":
            print(f"  {r.task_id}: {r.action} (score={r.complexity_score:.2f})")


if __name__ == "__main__":
    main()
