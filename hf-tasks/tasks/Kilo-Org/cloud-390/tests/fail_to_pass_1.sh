#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd cloudflare-app-builder && pnpm exec vitest run src/git/git-protocol-info-refs.test.ts
