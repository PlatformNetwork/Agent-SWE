#!/bin/bash
# This test must PASS on base commit AND after fix
pytest tests/test_load.py::test_load_media -q -o addopts=''
