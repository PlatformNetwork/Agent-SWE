#!/bin/bash
# This test must PASS on base commit AND after fix
pnpm vitest run packages/ui/src/atoms/Button/Button.test.tsx
