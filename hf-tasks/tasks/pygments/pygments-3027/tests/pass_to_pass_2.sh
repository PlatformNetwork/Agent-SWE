#!/bin/bash
# This test must PASS on base commit AND after fix
pytest tests/snippets/toml -q
