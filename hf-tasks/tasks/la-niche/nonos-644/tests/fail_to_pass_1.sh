#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q tests/test_deprecated_rotation_params.py
