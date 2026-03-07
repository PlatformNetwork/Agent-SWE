#!/bin/bash
# This test must FAIL on base commit, PASS after fix
yarn workspace @agoric/internal test test/typescript-upgrade.test.js
