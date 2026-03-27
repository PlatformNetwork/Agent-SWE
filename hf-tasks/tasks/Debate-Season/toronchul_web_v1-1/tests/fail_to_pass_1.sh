#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm run build && node tests/typography-tokens.test.js
