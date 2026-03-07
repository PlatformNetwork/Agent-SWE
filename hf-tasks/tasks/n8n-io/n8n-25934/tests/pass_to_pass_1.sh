#!/bin/bash
# This test must PASS on base commit AND after fix
pnpm --filter @n8n/workflow-sdk test -- --runTestsByPath src/utils/safe-access.test.ts
