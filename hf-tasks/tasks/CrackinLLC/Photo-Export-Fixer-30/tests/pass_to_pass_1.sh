#!/bin/bash
# This test must PASS on base commit AND after fix
pytest pef/tests/test_utils.py -q
