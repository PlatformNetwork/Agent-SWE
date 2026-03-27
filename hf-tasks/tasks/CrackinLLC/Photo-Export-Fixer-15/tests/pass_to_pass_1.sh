#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q pef/tests/test_orchestrator.py::TestPEFOrchestratorDryRun::test_returns_dry_run_result
