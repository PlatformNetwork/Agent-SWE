#!/bin/bash
# This test must PASS on base commit AND after fix
pytest tests/slow/adrio/cdc_test.py -k "covid_state_hospitalization" -q
