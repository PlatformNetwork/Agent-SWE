#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q test/unit_tests/datasets/test_dataset.py::test_len_base_dataset
