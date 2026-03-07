#!/bin/bash
# This test must FAIL on base commit, PASS after fix
python -m nose2 -s test/unit -v test_object_keys
