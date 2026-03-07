#!/bin/bash
# This test must PASS on base commit AND after fix
pytest -q tests/unit/admin/views/test_sponsors.py::TestSponsorForm
