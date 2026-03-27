#!/bin/bash
# This test must PASS on base commit AND after fix
pytest tests/test_cli_pool.py -k "not test_rejects_code_execution"
