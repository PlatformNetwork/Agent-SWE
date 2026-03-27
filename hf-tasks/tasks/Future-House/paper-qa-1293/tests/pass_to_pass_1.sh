#!/bin/bash
# This test must PASS on base commit AND after fix
pytest tests/test_configs.py::test_router_kwargs_present_in_models -q
