#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npx vitest run --config apps/mohang-app/vite.config.mts apps/mohang-app/src/app/pages/auth-code-check-logging.spec.ts
