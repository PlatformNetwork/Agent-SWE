#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- src/next-config.headers.test.ts
