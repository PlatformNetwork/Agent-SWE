#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pytest -q test/unit_tests/datasets/test_dataset_repr.py
