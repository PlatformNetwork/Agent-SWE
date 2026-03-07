#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pnpm --filter @n8n/workflow-sdk test -- --runTestsByPath src/expression-public-surface.test.ts
