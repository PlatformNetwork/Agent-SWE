#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pnpm exec tsx tests/megaeth-explorer.test.ts
