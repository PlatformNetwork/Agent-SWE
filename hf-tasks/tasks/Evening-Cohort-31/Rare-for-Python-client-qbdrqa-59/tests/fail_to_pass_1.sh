#!/bin/bash
# This test must FAIL on base commit, PASS after fix
CI=true npm test -- --watchAll=false
