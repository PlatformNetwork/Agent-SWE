#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pnpm vitest run packages/markdown/__tests__/tilde-code-block.spec.ts
