"""Pipeline orchestrator for SWE mining workflow.

This module wires together all pipeline stages:
GH Archive -> Enricher -> Filter -> LLM Classify -> Extract -> Export

Uses aggressive parallelism with semaphores controlling concurrency at each stage.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from .enricher import EnrichedPullRequest, enrich_pr
from .filters import FilterConfig, apply_filters
from .gharchive import GhArchiveClient, GhArchiveEvent
from .github_api import GitHubClient
from .models import SweTask, SweTaskStatus

logger = logging.getLogger(__name__)


class SwePipelineEventType(str, Enum):
    """Types of events emitted during pipeline execution."""

    COLLECTION_STARTED = "collection_started"
    CANDIDATE_FILTERED = "candidate_filtered"
    TASK_EXTRACTED = "task_extracted"
    QUALITY_SCORED = "quality_scored"
    PIPELINE_COMPLETED = "pipeline_completed"


@dataclass
class SwePipelineEvent:
    """Event emitted during pipeline execution for progress tracking."""

    event_type: SwePipelineEventType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DifficultyTargets:
    """Per-difficulty quotas for multi-target mining mode."""

    targets: dict[str, int] = field(default_factory=dict)

    def all_met(self, counts: dict[str, int]) -> bool:
        """Check if all difficulty quotas are met."""
        return all(
            counts.get(level, 0) >= quota for level, quota in self.targets.items()
        )


@dataclass
class SwePipelineConfig:
    """Configuration for the SWE mining pipeline.

    Attributes:
        min_stars: Minimum GitHub stars required for a repository.
        languages: List of allowed programming languages (empty = all).
        max_candidates: Maximum PR candidates to process.
        max_tasks: Maximum tasks to extract before stopping.
        once: If True, stop after max_tasks; otherwise run continuously.
        concurrency_enrich: Max concurrent enrichment operations.
        concurrency_preclassify: Max concurrent pre-classification LLM calls.
        concurrency_deep: Max concurrent deep processing operations.
        difficulty_filter: Filter for specific difficulty level.
        difficulty_targets: Per-difficulty quotas for multi-target mode.
    """

    min_stars: int = 20
    languages: list[str] = field(default_factory=list)
    max_candidates: int = 50
    max_tasks: int = 1
    once: bool = True
    concurrency_enrich: int = 20
    concurrency_preclassify: int = 25
    concurrency_deep: int = 8
    difficulty_filter: str | None = None
    difficulty_targets: DifficultyTargets | None = None


@dataclass
class BenchmarkMetrics:
    """Aggregate metrics collected during a full pipeline run."""

    total_raw_events: int = 0
    total_merged_events: int = 0
    total_prefiltered: int = 0
    enriched_count: int = 0
    enrichment_failed: int = 0
    filter_passed: int = 0
    filter_rejected: int = 0
    filter_rejection_reasons: dict[str, int] = field(default_factory=dict)
    preclassify_count: int = 0
    preclassify_easy: int = 0
    preclassify_medium: int = 0
    preclassify_hard: int = 0
    extraction_attempted: int = 0
    extraction_succeeded: int = 0
    extraction_failed: int = 0
    quality_scored: int = 0
    quality_passed: int = 0
    quality_failed: int = 0
    difficulty_easy: int = 0
    difficulty_medium: int = 0
    difficulty_hard: int = 0
    accepted_count: int = 0
    total_processing_time_ms: float = 0.0
    avg_per_pr_time_ms: float = 0.0
    throughput_prs_per_sec: float = 0.0
    avg_quality_score: float = 0.0
    languages: dict[str, int] = field(default_factory=dict)


@dataclass
class SwePipelineRunResult:
    """Result of a pipeline run."""

    tasks: list[SweTask] = field(default_factory=list)
    filtered: int = 0
    extracted: int = 0
    scored: int = 0
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    benchmark_metrics: BenchmarkMetrics | None = None


class SwePipeline:
    """Orchestrates the SWE mining pipeline stages.

    Pipeline stages (in order):
    1. Enrich: Fetch PR details from GitHub API
    2. Filter: Apply local filters (fast, no external calls)
    3. Pre-classify: LLM-based difficulty classification
    4. Deep: Extraction, test generation, quality scoring

    Uses semaphores to control concurrency at each stage.
    """

    def __init__(
        self,
        gh_client: GitHubClient,
        gh_archive_client: GhArchiveClient | None = None,
        config: SwePipelineConfig | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            gh_client: GitHub API client for enrichment.
            gh_archive_client: GH Archive client (or create default).
            config: Pipeline configuration.
        """
        self.gh_client = gh_client
        self.gh_archive_client = gh_archive_client or GhArchiveClient()
        self.config = config or SwePipelineConfig()
        self._filter_config = self._build_filter_config()
        self._active = False

    def _build_filter_config(self) -> FilterConfig:
        """Build filter config from pipeline config."""
        return FilterConfig(
            min_stars=self.config.min_stars,
            allowed_languages=self.config.languages
            if self.config.languages
            else ["python"],
            max_files_changed=50,
            exclude_bots=True,
        )

    async def __aenter__(self) -> "SwePipeline":
        """Enter async context manager."""
        if self.gh_archive_client._session is None:
            await self.gh_archive_client._ensure_session()
        self._active = True
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        self._active = False
        await self.gh_archive_client.close()

    async def _emit_event(
        self, queue: asyncio.Queue[SwePipelineEvent] | None, event: SwePipelineEvent
    ) -> None:
        """Emit an event to the progress queue if available."""
        if queue is not None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping event: %s", event.event_type)

    async def _enrich_stage(
        self,
        event: GhArchiveEvent,
        semaphore: asyncio.Semaphore,
        metrics: BenchmarkMetrics,
    ) -> EnrichedPullRequest | None:
        """Stage 1: Enrich a GH Archive event with GitHub API data."""
        async with semaphore:
            try:
                enriched = await enrich_pr(event, self.gh_client)
                metrics.enriched_count += 1
                return enriched
            except Exception as e:
                logger.warning(
                    "Enrichment failed for %s#%d: %s",
                    event.repository,
                    event.pull_number,
                    e,
                )
                metrics.enrichment_failed += 1
                return None

    def _filter_stage(
        self,
        enriched: EnrichedPullRequest,
        metrics: BenchmarkMetrics,
    ) -> bool:
        """Stage 2: Apply local filters (pure Python, fast)."""
        passed = apply_filters(enriched, self._filter_config)
        if passed:
            metrics.filter_passed += 1
        else:
            metrics.filter_rejected += 1
        return passed

    async def _preclassify_stage(
        self,
        enriched: EnrichedPullRequest,
        semaphore: asyncio.Semaphore,
        metrics: BenchmarkMetrics,
    ) -> str | None:
        """Stage 3: Pre-classify difficulty using LLM.

        For now, returns a mock difficulty based on file count.
        In production, this would call an LLM.
        """
        async with semaphore:
            # Mock classification logic based on heuristics
            # In production, this would call LLM difficulty classifier
            metrics.preclassify_count += 1

            if enriched.files_changed <= 2:
                difficulty = "easy"
                metrics.preclassify_easy += 1
            elif enriched.files_changed <= 5:
                difficulty = "medium"
                metrics.preclassify_medium += 1
            else:
                difficulty = "hard"
                metrics.preclassify_hard += 1

            logger.debug(
                "Pre-classified %s#%d as %s",
                enriched.repo,
                enriched.number,
                difficulty,
            )
            return difficulty

    async def _deep_stage(
        self,
        enriched: EnrichedPullRequest,
        semaphore: asyncio.Semaphore,
        metrics: BenchmarkMetrics,
        event_queue: asyncio.Queue[SwePipelineEvent] | None,
    ) -> SweTask | None:
        """Stage 4: Deep processing (extraction, quality scoring).

        For now, creates a basic task without actual extraction.
        In production, this would run patch extraction, test generation, etc.
        """
        async with semaphore:
            metrics.extraction_attempted += 1

            try:
                # Create basic task from enriched PR
                task = SweTask(
                    id=f"{enriched.repo.replace('/', '-')}-{enriched.number}",
                    repo=enriched.repo,
                    base_commit=enriched.base_commit,
                    merge_commit=enriched.merge_commit,
                    language=enriched.language,
                    prompt=enriched.title,
                    original_pr_body=enriched.body or "",
                    status=SweTaskStatus.CANDIDATE,
                )

                metrics.extraction_succeeded += 1

                # Mock quality scoring
                quality_score = 0.75 + (len(enriched.changed_files) * 0.02)
                quality_score = min(quality_score, 1.0)
                task.quality_score = quality_score
                task.quality_passed = quality_score >= 0.7

                metrics.quality_scored += 1
                if task.quality_passed:
                    metrics.quality_passed += 1
                else:
                    metrics.quality_failed += 1

                # Set difficulty
                if enriched.files_changed <= 2:
                    task.difficulty_score = 1
                    metrics.difficulty_easy += 1
                elif enriched.files_changed <= 5:
                    task.difficulty_score = 2
                    metrics.difficulty_medium += 1
                else:
                    task.difficulty_score = 3
                    metrics.difficulty_hard += 1

                # Emit quality scored event
                await self._emit_event(
                    event_queue,
                    SwePipelineEvent(
                        SwePipelineEventType.QUALITY_SCORED,
                        {
                            "task_id": task.id,
                            "score": quality_score,
                            "passed": task.quality_passed,
                        },
                    ),
                )

                logger.info(
                    "Task %s processed (score=%.2f, passed=%s)",
                    task.id,
                    quality_score,
                    task.quality_passed,
                )
                return task

            except Exception as e:
                metrics.extraction_failed += 1
                logger.warning(
                    "Deep processing failed for %s#%d: %s",
                    enriched.repo,
                    enriched.number,
                    e,
                )
                return None

    def _should_skip_event(self, event: GhArchiveEvent) -> bool:
        """Pre-filter events before enrichment."""
        if event.pull_number == 0:
            return True
        if "[bot]" in event.actor or event.actor == "dependabot":
            return True
        if not event.has_org:
            return True
        return False

    def _difficulty_matches_filter(
        self, difficulty: str | None, config: SwePipelineConfig
    ) -> bool:
        """Check if difficulty matches the configured filter."""
        if config.difficulty_targets is not None:
            return difficulty in config.difficulty_targets.targets
        if config.difficulty_filter is not None:
            return difficulty == config.difficulty_filter
        return True  # No filter, all pass

    async def run(self) -> SwePipelineRunResult:
        """Run the pipeline and return results.

        This is a convenience method that collects all events.
        For progress tracking, use run_with_progress() instead.
        """
        tasks: list[SweTask] = []
        metrics = BenchmarkMetrics()
        filtered_count = 0

        async for event in self.run_with_progress():
            if event.event_type == SwePipelineEventType.TASK_EXTRACTED:
                task_data = event.data.get("task")
                if task_data and isinstance(task_data, SweTask):
                    tasks.append(task_data)
            elif event.event_type == SwePipelineEventType.CANDIDATE_FILTERED:
                if not event.data.get("accepted", True):
                    filtered_count += 1

        # Calculate final metrics
        if metrics.enriched_count > 0:
            metrics.throughput_prs_per_sec = metrics.enriched_count / max(
                metrics.total_processing_time_ms / 1000.0, 0.001
            )
            metrics.avg_per_pr_time_ms = (
                metrics.total_processing_time_ms / metrics.enriched_count
            )

        return SwePipelineRunResult(
            tasks=tasks,
            filtered=filtered_count,
            extracted=len(tasks),
            scored=metrics.quality_scored,
            benchmark_metrics=metrics,
        )

    async def run_with_progress(
        self,
    ) -> AsyncGenerator[SwePipelineEvent, None]:
        """Run the pipeline yielding progress events.

        Yields events as tasks progress through the pipeline stages.
        """
        start_time = datetime.now(timezone.utc)
        metrics = BenchmarkMetrics()

        # Create semaphores for concurrency control
        enrich_sem = asyncio.Semaphore(self.config.concurrency_enrich)
        preclassify_sem = asyncio.Semaphore(self.config.concurrency_preclassify)
        deep_sem = asyncio.Semaphore(self.config.concurrency_deep)

        # Create event queue for progress tracking
        event_queue: asyncio.Queue[SwePipelineEvent] = asyncio.Queue(maxsize=1000)

        # Emit collection started
        yield SwePipelineEvent(
            SwePipelineEventType.COLLECTION_STARTED,
            {"requested": self.config.max_candidates},
        )

        # Calculate hours back based on candidates
        hours_back = min(max((self.config.max_candidates // 50) + 1, 6), 12)

        # Fetch events from GH Archive
        try:
            # For testing, we might have mock events
            events = await self._fetch_events(hours_back)
        except Exception as e:
            logger.error("Failed to fetch GH Archive events: %s", e)
            yield SwePipelineEvent(
                SwePipelineEventType.PIPELINE_COMPLETED,
                {"emitted": 0, "error": str(e)},
            )
            return

        metrics.total_raw_events = len(events)

        # Filter to merged PRs only
        events = [e for e in events if e.action.lower() == "merged"]
        metrics.total_merged_events = len(events)

        # Pre-filter events
        events = [e for e in events if not self._should_skip_event(e)]
        metrics.total_prefiltered = len(events)

        if not events:
            logger.warning("No merged PRs found in GH Archive data")
            yield SwePipelineEvent(
                SwePipelineEventType.PIPELINE_COMPLETED,
                {"emitted": 0, "error": "No merged PRs found"},
            )
            return

        # Shuffle for diversity
        random.shuffle(events)

        # Truncate to max candidates
        if self.config.max_candidates > 0 and len(events) > self.config.max_candidates:
            events = events[: self.config.max_candidates]

        # Track completed tasks and per-difficulty counts
        completed_count = 0
        per_difficulty_counts: dict[str, int] = {}
        accepted_tasks: list[SweTask] = []

        # Process events through pipeline stages
        pending_tasks: list[asyncio.Task] = []

        async def process_event(event: GhArchiveEvent) -> SweTask | None:
            """Process a single event through all stages."""
            nonlocal completed_count

            # Check if we've reached the target
            if self.config.once:
                if self.config.difficulty_targets is not None:
                    if self.config.difficulty_targets.all_met(per_difficulty_counts):
                        return None
                elif completed_count >= self.config.max_tasks:
                    return None

            # Stage 1: Enrich
            enriched = await self._enrich_stage(event, enrich_sem, metrics)
            if enriched is None:
                return None

            # Basic validation
            if enriched.title == "Untitled change" or not enriched.merge_commit:
                return None

            if enriched.files_changed == 0:
                return None

            # Stage 2: Filter
            if not self._filter_stage(enriched, metrics):
                await self._emit_event(
                    event_queue,
                    SwePipelineEvent(
                        SwePipelineEventType.CANDIDATE_FILTERED,
                        {
                            "event_id": event.id,
                            "accepted": False,
                            "reasons": ["filter_rejected"],
                        },
                    ),
                )
                return None

            # Emit filter passed
            await self._emit_event(
                event_queue,
                SwePipelineEvent(
                    SwePipelineEventType.CANDIDATE_FILTERED,
                    {"event_id": event.id, "accepted": True, "reasons": []},
                ),
            )

            # Check again after filter
            if self.config.once:
                if self.config.difficulty_targets is not None:
                    if self.config.difficulty_targets.all_met(per_difficulty_counts):
                        return None
                elif completed_count >= self.config.max_tasks:
                    return None

            # Stage 3: Pre-classify
            difficulty = await self._preclassify_stage(
                enriched, preclassify_sem, metrics
            )

            # Apply difficulty filter
            if not self._difficulty_matches_filter(difficulty, self.config):
                logger.debug(
                    "Difficulty %s does not match filter for %s#%d",
                    difficulty,
                    enriched.repo,
                    enriched.number,
                )
                return None

            # Check per-difficulty quota
            if self.config.difficulty_targets is not None and difficulty:
                current = per_difficulty_counts.get(difficulty, 0)
                quota = self.config.difficulty_targets.targets.get(difficulty, 0)
                if quota > 0 and current >= quota:
                    return None

            # Stage 4: Deep processing
            task = await self._deep_stage(enriched, deep_sem, metrics, event_queue)
            if task is None:
                return None

            if task.quality_passed:
                # Update task status
                task.status = SweTaskStatus.READY
                metrics.accepted_count += 1

                # Track language
                if task.language:
                    metrics.languages[task.language] = (
                        metrics.languages.get(task.language, 0) + 1
                    )

                # Track per-difficulty
                if difficulty:
                    per_difficulty_counts[difficulty] = (
                        per_difficulty_counts.get(difficulty, 0) + 1
                    )

                completed_count += 1

                return task

            return None

        # Run all events concurrently (semaphores control actual concurrency)
        for event in events:
            task = asyncio.create_task(process_event(event))
            pending_tasks.append(task)

        # Wait for all tasks and yield events
        for coro in asyncio.as_completed(pending_tasks):
            try:
                result = await coro
                if result is not None:
                    accepted_tasks.append(result)
                    yield SwePipelineEvent(
                        SwePipelineEventType.TASK_EXTRACTED,
                        {"task": result, "task_id": result.id},
                    )

                    # Check if we should stop
                    if self.config.once:
                        if self.config.difficulty_targets is not None:
                            if self.config.difficulty_targets.all_met(
                                per_difficulty_counts
                            ):
                                break
                        elif completed_count >= self.config.max_tasks:
                            break
            except Exception as e:
                logger.warning("Event processing failed: %s", e)

        # Calculate timing metrics
        end_time = datetime.now(timezone.utc)
        metrics.total_processing_time_ms = (
            end_time - start_time
        ).total_seconds() * 1000

        if metrics.enriched_count > 0:
            metrics.avg_per_pr_time_ms = (
                metrics.total_processing_time_ms / metrics.enriched_count
            )
            metrics.throughput_prs_per_sec = metrics.enriched_count / max(
                metrics.total_processing_time_ms / 1000.0, 0.001
            )

        # Yield remaining queued events
        while not event_queue.empty():
            yield event_queue.get_nowait()

        # Emit completion
        yield SwePipelineEvent(
            SwePipelineEventType.PIPELINE_COMPLETED,
            {"emitted": len(accepted_tasks), "metrics": metrics},
        )

    async def _fetch_events(self, hours_back: int) -> list[GhArchiveEvent]:
        """Fetch events from GH Archive.

        Subclasses can override this for testing.
        """
        from datetime import timedelta

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=hours_back)

        return await self.gh_archive_client.fetch_merged_prs(
            start_date, end_date, skip_missing=True
        )


async def run_pipeline_once(
    gh_client: GitHubClient,
    config: SwePipelineConfig | None = None,
) -> SwePipelineRunResult:
    """Convenience function to run the pipeline once.

    Args:
        gh_client: GitHub API client.
        config: Pipeline configuration.

    Returns:
        Pipeline run result with extracted tasks.
    """
    async with SwePipeline(gh_client, config=config or SwePipelineConfig()) as pipeline:
        return await pipeline.run()
