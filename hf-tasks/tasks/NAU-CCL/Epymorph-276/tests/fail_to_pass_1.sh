#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest tests/fast/adrio/cdc_daily_test.py -q
