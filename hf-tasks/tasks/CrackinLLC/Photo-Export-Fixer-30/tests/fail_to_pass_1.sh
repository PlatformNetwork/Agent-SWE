#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest pef/tests/test_gui_pr_updates.py -q
