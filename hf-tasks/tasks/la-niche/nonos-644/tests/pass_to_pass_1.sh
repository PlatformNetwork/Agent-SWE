#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q tests/test_parse_planet_inputs.py::TestParseRotationAngle::test_from_rotate_with
