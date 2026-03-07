#!/bin/bash
# This test must FAIL on base commit, PASS after fix
bash -lc "make test > /tmp/make_test_output.txt 2>&1; grep -q 'mocha -r ts-node/register' /tmp/make_test_output.txt"
