#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q test/dialects/databricks_materialized_view_test.py
