#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q tests/test_telegram_help_access.py
