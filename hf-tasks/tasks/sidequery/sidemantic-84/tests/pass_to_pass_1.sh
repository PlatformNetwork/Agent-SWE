#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q tests/test_drill_down_api.py::test_get_hierarchy_path
