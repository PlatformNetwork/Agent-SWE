#!/bin/bash
# This test must PASS on base commit AND after fix
cd cloudflare-app-builder && pnpm exec vitest run src/git/git-receive-pack-service.test.ts
