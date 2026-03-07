#!/bin/bash
# This test must PASS on base commit AND after fix
pnpm vitest run packages/markdown/__tests__/manager.spec.ts
