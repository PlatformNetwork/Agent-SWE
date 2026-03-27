#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q tests/unit/admin/templates/test_sponsor_admin_templates.py
