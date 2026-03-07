#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q tests/test_commands.py
