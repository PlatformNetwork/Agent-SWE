#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q pef/tests/test_dry_run_cancellation.py
