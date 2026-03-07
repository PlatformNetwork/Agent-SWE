#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q tests/federation/test_utils.py
