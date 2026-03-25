"""Tests for progress monitoring."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from swe_forge.swe.progress import (
    ProgressCounters,
    ProgressMonitor,
    ProgressSnapshot,
)


class TestProgressSnapshot:
    def test_default_values(self):
        snap = ProgressSnapshot()
        assert snap.filtered == 0
        assert snap.extracted == 0
        assert snap.scored == 0
        assert snap.accepted == 0
        assert snap.enriched == 0
        assert snap.preclassified == 0
        assert snap.deep_processing == 0
        assert snap.docker_active == 0
        assert snap.elapsed_seconds == 0.0

    def test_custom_values(self):
        snap = ProgressSnapshot(
            filtered=10,
            extracted=8,
            scored=5,
            accepted=3,
            enriched=15,
            preclassified=12,
            deep_processing=2,
            docker_active=1,
            elapsed_seconds=42.5,
        )
        assert snap.filtered == 10
        assert snap.extracted == 8
        assert snap.scored == 5
        assert snap.accepted == 3
        assert snap.enriched == 15
        assert snap.preclassified == 12
        assert snap.deep_processing == 2
        assert snap.docker_active == 1
        assert snap.elapsed_seconds == 42.5


class TestProgressCounters:
    def test_initial_counters_zero(self):
        counters = ProgressCounters()
        for name in [
            "filtered",
            "extracted",
            "scored",
            "accepted",
            "enriched",
            "preclassified",
            "deep_processing",
            "docker_active",
        ]:
            assert counters.get(name) == 0

    def test_increment_default_delta(self):
        counters = ProgressCounters()
        counters.increment("filtered")
        assert counters.get("filtered") == 1
        counters.increment("filtered")
        assert counters.get("filtered") == 2

    def test_increment_custom_delta(self):
        counters = ProgressCounters()
        counters.increment("enriched", 5)
        assert counters.get("enriched") == 5
        counters.increment("enriched", -2)
        assert counters.get("enriched") == 3

    def test_invalid_counter_name_raises(self):
        counters = ProgressCounters()
        with pytest.raises(KeyError, match="Unknown counter"):
            counters.increment("invalid_counter")
        with pytest.raises(KeyError, match="Unknown counter"):
            counters.get("invalid_counter")

    def test_snapshot_elapsed_time(self):
        counters = ProgressCounters()
        start = time.time()
        counters.increment("filtered", 10)
        time.sleep(0.05)
        snap = counters.snapshot(start)
        assert snap.elapsed_seconds >= 0.05
        assert snap.filtered == 10

    def test_snapshot_all_counters(self):
        counters = ProgressCounters()
        counters.increment("filtered", 5)
        counters.increment("extracted", 4)
        counters.increment("scored", 3)
        counters.increment("accepted", 2)
        counters.increment("enriched", 1)
        counters.increment("preclassified", 10)
        counters.increment("deep_processing", 7)
        counters.increment("docker_active", 3)

        start = time.time()
        snap = counters.snapshot(start)

        assert snap.filtered == 5
        assert snap.extracted == 4
        assert snap.scored == 3
        assert snap.accepted == 2
        assert snap.enriched == 1
        assert snap.preclassified == 10
        assert snap.deep_processing == 7
        assert snap.docker_active == 3

    def test_thread_safety_concurrent_increments(self):
        counters = ProgressCounters()
        num_threads = 10
        increments_per_thread = 1000

        def increment_thread():
            for _ in range(increments_per_thread):
                counters.increment("filtered")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(increment_thread) for _ in range(num_threads)]
            for f in futures:
                f.result()

        assert counters.get("filtered") == num_threads * increments_per_thread

    def test_thread_safety_multiple_counters(self):
        counters = ProgressCounters()

        def increment_filtered():
            for _ in range(500):
                counters.increment("filtered")

        def increment_enriched():
            for _ in range(300):
                counters.increment("enriched")

        def increment_accepted():
            for _ in range(200):
                counters.increment("accepted")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(increment_filtered),
                executor.submit(increment_enriched),
                executor.submit(increment_accepted),
            ]
            for f in futures:
                f.result()

        assert counters.get("filtered") == 500
        assert counters.get("enriched") == 300
        assert counters.get("accepted") == 200


class TestProgressMonitor:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        counters = ProgressCounters()
        monitor = ProgressMonitor.start(counters, max_tasks=100, interval=0.1)
        assert monitor._task is not None
        assert not monitor._task.done()
        await monitor.stop()
        assert monitor._task.done()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        counters = ProgressCounters()
        monitor = ProgressMonitor.start(counters, max_tasks=100, interval=0.1)
        await monitor.stop()
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_emits_progress_after_interval(self, monkeypatch):
        counters = ProgressCounters()
        counters.increment("filtered", 42)
        counters.increment("accepted", 10)

        emitted = []

        def mock_info(msg, **kwargs):
            emitted.append((msg, kwargs))

        monkeypatch.setattr(
            "swe_forge.swe.progress.logger.info",
            mock_info,
        )

        monitor = ProgressMonitor.start(counters, max_tasks=100, interval=0.1)
        await asyncio.sleep(0.15)
        await monitor.stop()

        assert any(msg == "pipeline_progress" for msg, _ in emitted)

    @pytest.mark.asyncio
    async def test_custom_interval(self):
        counters = ProgressCounters()
        monitor = ProgressMonitor.start(counters, max_tasks=100, interval=0.05)
        start = time.time()
        await asyncio.sleep(0.08)
        await monitor.stop()
        elapsed = time.time() - start
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_stops_immediately_when_stop_called(self):
        counters = ProgressCounters()
        monitor = ProgressMonitor.start(counters, max_tasks=100, interval=5.0)
        await asyncio.sleep(0.01)
        await monitor.stop()
        assert monitor._task.done()


class TestProgressIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_simulation(self, caplog):
        import logging

        logging.getLogger("swe_forge.swe.progress").setLevel(logging.INFO)

        counters = ProgressCounters()
        monitor = ProgressMonitor.start(counters, max_tasks=10, interval=0.05)

        counters.increment("filtered")
        counters.increment("extracted")
        counters.increment("enriched")
        counters.increment("preclassified")
        counters.increment("scored")
        await asyncio.sleep(0.08)

        counters.increment("accepted")
        counters.increment("docker_active", 2)

        await monitor.stop()

        snap = counters.snapshot(time.time())
        assert snap.filtered == 1
        assert snap.extracted == 1
        assert snap.enriched == 1
        assert snap.preclassified == 1
        assert snap.scored == 1
        assert snap.accepted == 1
