#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q test/dialects/dialects_test.py::test__dialect__base_file_parse --maxfail=1 -k "databricks and create_materialized_view"
