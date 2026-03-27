"""Tests for dry-run cancellation behavior in PEFOrchestrator."""

import threading

from pef.core.orchestrator import PEFOrchestrator


def test_dry_run_cancels_before_analysis(sample_takeout):
    """Cancellation before analysis should stop early and report cancelled."""
    orchestrator = PEFOrchestrator(sample_takeout)
    cancel_event = threading.Event()
    cancel_event.set()
    messages = []

    def capture_progress(current, total, message):
        messages.append(message)

    result = orchestrator.dry_run(on_progress=capture_progress, cancel_event=cancel_event)

    assert result.cancelled is True
    assert result.json_count > 0
    assert result.matched_count + result.unmatched_json_count < result.json_count
    assert any("Preview cancelled" in message for message in messages)


def test_dry_run_cancels_during_loop(sample_takeout):
    """Cancellation triggered during analysis should stop with partial results."""
    orchestrator = PEFOrchestrator(sample_takeout)
    cancel_event = threading.Event()
    messages = []

    def capture_progress(current, total, message):
        messages.append(message)
        if "Analyzing:" in message and not cancel_event.is_set():
            cancel_event.set()

    result = orchestrator.dry_run(on_progress=capture_progress, cancel_event=cancel_event)

    assert result.cancelled is True
    assert result.json_count > 0
    assert result.matched_count + result.unmatched_json_count < result.json_count
    assert any("Preview cancelled" in message for message in messages)


def test_dry_run_without_cancel_event_remains_compatible(sample_takeout):
    """Dry run should still complete normally when no cancel event is provided."""
    orchestrator = PEFOrchestrator(sample_takeout)
    result = orchestrator.dry_run()

    assert result.cancelled is False
    assert result.json_count > 0
    assert result.matched_count + result.unmatched_json_count == result.json_count
