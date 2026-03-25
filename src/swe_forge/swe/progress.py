"""Progress monitoring for SWE task processing pipeline.

Thread-safe counters and background monitor for tracking processing progress.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


@dataclass
class ProgressSnapshot:
    """Immutable snapshot of progress counters at a point in time."""

    filtered: int = 0
    extracted: int = 0
    scored: int = 0
    accepted: int = 0
    enriched: int = 0
    preclassified: int = 0
    deep_processing: int = 0
    docker_active: int = 0
    elapsed_seconds: float = 0.0


class ProgressCounters:
    """Thread-safe progress counters using threading.Lock.

    Tracks various processing stages for SWE task pipeline.
    Counter increment timing:
    - `enriched`: After successful GitHub API enrichment
    - `filtered`: After filter stage (passed + rejected)
    - `preclassified`: After pre-classification (cached or fresh)
    - `scored`: After quality assessment
    - `accepted`: After task accepted into final output
    - `extracted`: When added to tasks list
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {
            "filtered": 0,
            "extracted": 0,
            "scored": 0,
            "accepted": 0,
            "enriched": 0,
            "preclassified": 0,
            "deep_processing": 0,
            "docker_active": 0,
        }

    def increment(self, name: str, delta: int = 1) -> None:
        """Increment a counter by the given delta.

        Args:
            name: Counter name (filtered, extracted, scored, accepted, enriched,
                  preclassified, deep_processing, docker_active).
            delta: Amount to increment by (default: 1).

        Raises:
            KeyError: If counter name is invalid.
        """
        with self._lock:
            if name not in self._counters:
                raise KeyError(f"Unknown counter: {name}")
            self._counters[name] += delta

    def get(self, name: str) -> int:
        """Get current value of a counter.

        Args:
            name: Counter name.

        Returns:
            Current counter value.

        Raises:
            KeyError: If counter name is invalid.
        """
        with self._lock:
            if name not in self._counters:
                raise KeyError(f"Unknown counter: {name}")
            return self._counters[name]

    def snapshot(self, start_time: float) -> ProgressSnapshot:
        """Create an immutable snapshot of all counters.

        Args:
            start_time: Start time as returned by time.time().

        Returns:
            ProgressSnapshot with current counter values and elapsed time.
        """
        elapsed = time.time() - start_time
        with self._lock:
            return ProgressSnapshot(
                filtered=self._counters["filtered"],
                extracted=self._counters["extracted"],
                scored=self._counters["scored"],
                accepted=self._counters["accepted"],
                enriched=self._counters["enriched"],
                preclassified=self._counters["preclassified"],
                deep_processing=self._counters["deep_processing"],
                docker_active=self._counters["docker_active"],
                elapsed_seconds=elapsed,
            )


class ProgressMonitor:
    """Background task that logs progress at regular intervals.

    Logs structured progress message every interval seconds with:
    - Counter values
    - Elapsed time
    - Tasks per second throughput
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @classmethod
    def start(
        cls,
        counters: ProgressCounters,
        max_tasks: int,
        interval: float = 30.0,
    ) -> ProgressMonitor:
        """Create and start a progress monitor.

        Args:
            counters: ProgressCounters instance to monitor.
            max_tasks: Expected total number of tasks.
            interval: Logging interval in seconds (default: 30.0).

        Returns:
            Running ProgressMonitor instance.
        """
        monitor = cls()
        start_time = time.time()
        monitor._task = asyncio.create_task(
            monitor._monitor_loop(counters, start_time, max_tasks, interval)
        )
        return monitor

    async def _monitor_loop(
        self,
        counters: ProgressCounters,
        start_time: float,
        max_tasks: int,
        interval: float,
    ) -> None:
        """Monitor loop that logs progress periodically.

        Args:
            counters: ProgressCounters to monitor.
            start_time: Start time for elapsed calculation.
            max_tasks: Expected total number of tasks.
            interval: Logging interval in seconds.
        """
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                # stop_event was set, exit loop
                break
            except asyncio.TimeoutError:
                # Timeout reached, emit progress
                snap = counters.snapshot(start_time)
                self._emit_progress(snap, max_tasks)

    def _emit_progress(self, snap: ProgressSnapshot, max_tasks: int) -> None:
        """Emit structured progress log message.

        Args:
            snap: ProgressSnapshot with current values.
            max_tasks: Expected total number of tasks.
        """
        tasks_per_sec = (
            snap.filtered / snap.elapsed_seconds if snap.elapsed_seconds > 0 else 0.0
        )

        logger.info(
            "pipeline_progress",
            filtered=snap.filtered,
            extracted=snap.extracted,
            scored=snap.scored,
            accepted=snap.accepted,
            enriched=snap.enriched,
            preclassified=snap.preclassified,
            deep_processing=snap.deep_processing,
            docker_active=snap.docker_active,
            max_tasks=max_tasks,
            elapsed_seconds=round(snap.elapsed_seconds, 2),
            tasks_per_second=round(tasks_per_sec, 2),
        )

    async def stop(self) -> None:
        """Stop the progress monitor and wait for it to finish."""
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass


__all__ = [
    "ProgressSnapshot",
    "ProgressCounters",
    "ProgressMonitor",
]
