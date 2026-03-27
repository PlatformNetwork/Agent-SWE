#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest tests/test_load_media_missing.py -q -o addopts=''
