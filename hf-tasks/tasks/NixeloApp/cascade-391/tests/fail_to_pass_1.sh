#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm run test:convex:run -- convex/authWrapperPasswordReset.test.ts
