#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest tests/test_toml_1_1_lexer.py -q
