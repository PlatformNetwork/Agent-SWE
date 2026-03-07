#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest tests/test_cache_control.py -q
