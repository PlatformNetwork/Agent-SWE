#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- --project zero-cache/no-pg packages/zero-cache/src/services/change-source/pg/replica-cleanup.test.ts
