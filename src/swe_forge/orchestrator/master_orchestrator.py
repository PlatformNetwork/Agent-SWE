"""MasterOrchestrator - Coordinates multiple dataset orchestrators in parallel.

This module provides the master orchestrator that distributes tasks to N parallel
DatasetOrchestrator workers using asyncio.Semaphore for concurrency control.

Usage:
    master = MasterOrchestrator(parallel=5, llm_client=client)
    stats = await master.run_all(tasks)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .dataset_orchestrator import DatasetOrchestrator
from .models import OrchestratorStats, OrchestratorTask, TaskState

if TYPE_CHECKING:
    from swe_forge.llm.client import LLMClient

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """Coordinates multiple dataset orchestrators in parallel.

    Distributes tasks to N parallel workers and aggregates results.
    Uses asyncio.Semaphore for concurrency control to limit the number
    of simultaneous pipeline executions.

    Attributes:
        parallel: Maximum number of concurrent workers.
        llm_client: LLM client for test generation and repair.
        hf_token: HuggingFace API token for publishing.
        min_score_threshold: Minimum score required to publish.
        max_repair_attempts: Maximum repair attempts before rejecting.
        model: Model to use for LLM operations.
        docker_username: Docker Hub username for image naming.
        push_images: Whether to push Docker images to registry.
    """

    def __init__(
        self,
        parallel: int = 5,
        llm_client: LLMClient | None = None,
        hf_token: str | None = None,
        min_score_threshold: float = 0.5,
        max_repair_attempts: int = 5,
        model: str = "openai/gpt-4o",
        docker_username: str = "swe-forge",
        push_images: bool = False,
    ) -> None:
        """Initialize the MasterOrchestrator.

        Args:
            parallel: Maximum number of concurrent workers (default: 5).
            llm_client: LLM client for test generation and repair.
            hf_token: HuggingFace API token for publishing.
            min_score_threshold: Minimum score required to publish (default: 0.5).
            max_repair_attempts: Maximum repair attempts before rejecting (default: 5).
            model: Model to use for LLM operations (default: gpt-4o).
            docker_username: Docker Hub username for image naming.
            push_images: Whether to push Docker images to registry.
        """
        self.parallel = parallel
        self.llm_client = llm_client
        self.hf_token = hf_token
        self.min_score_threshold = min_score_threshold
        self.max_repair_attempts = max_repair_attempts
        self.model = model
        self.docker_username = docker_username
        self.push_images = push_images
        self._stats = OrchestratorStats()

    @property
    def stats(self) -> OrchestratorStats:
        """Get current aggregated statistics."""
        return self._stats

    async def run_all(self, tasks: list[OrchestratorTask]) -> OrchestratorStats:
        """Run all tasks in parallel with semaphore control.

        Distributes tasks to N parallel workers using asyncio.Semaphore
        for concurrency control. Each worker runs the full pipeline
        (Generate -> Validate -> Build -> Verify -> Repair -> Score -> Publish).

        Args:
            tasks: List of tasks to process.

        Returns:
            OrchestratorStats with aggregated results including state counts,
            pass rate, and timing information.
        """
        if not tasks:
            logger.warning("No tasks to process")
            return self._stats

        self._stats = OrchestratorStats(total_tasks=len(tasks))
        semaphore = asyncio.Semaphore(self.parallel)

        async def worker(
            task: OrchestratorTask, worker_id: int
        ) -> OrchestratorTask | Exception:
            """Worker that processes a single task with semaphore control."""
            async with semaphore:
                try:
                    orchestrator = DatasetOrchestrator(
                        orchestrator_id=worker_id,
                        llm_client=self.llm_client,
                        hf_token=self.hf_token,
                        min_score_threshold=self.min_score_threshold,
                        max_repair_attempts=self.max_repair_attempts,
                        model=self.model,
                        docker_username=self.docker_username,
                        push_images=self.push_images,
                    )
                    return await orchestrator.run_pipeline(task)
                except Exception as e:
                    logger.error(f"Worker {worker_id} crashed: {e}")
                    return e

        results = await asyncio.gather(
            *[worker(task, i) for i, task in enumerate(tasks)],
            return_exceptions=False,
        )

        self._aggregate_results(results, tasks)

        logger.info(
            f"Completed {self._stats.total_tasks} tasks: "
            f"{self._stats.state_counts.get(TaskState.COMPLETED, 0)} completed, "
            f"{self._stats.state_counts.get(TaskState.REJECTED, 0)} rejected, "
            f"{self._stats.state_counts.get(TaskState.FAILED, 0)} failed"
        )

        return self._stats

    def _aggregate_results(
        self,
        results: list[OrchestratorTask | Exception],
        original_tasks: list[OrchestratorTask],
    ) -> None:
        """Aggregate results from all workers into stats.

        Args:
            results: List of results from workers (either OrchestratorTask or Exception).
            original_tasks: Original list of tasks for reference.
        """
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._stats.state_counts[TaskState.FAILED] = (
                    self._stats.state_counts.get(TaskState.FAILED, 0) + 1
                )
                logger.error(
                    f"Task {original_tasks[i].task_id} failed with exception: {result}"
                )
            else:
                state = result.state
                self._stats.state_counts[state] = (
                    self._stats.state_counts.get(state, 0) + 1
                )

                if result.is_terminal():
                    created = result.created_at
                    updated = result.updated_at
                    elapsed = (updated - created).total_seconds()
                    self._stats.timing[result.task_id] = elapsed

    def __repr__(self) -> str:
        """Return string representation of the orchestrator."""
        return (
            f"MasterOrchestrator("
            f"parallel={self.parallel}, "
            f"min_score={self.min_score_threshold}, "
            f"max_repair={self.max_repair_attempts}"
            f")"
        )
