#!/bin/bash
# This test must FAIL on base commit, PASS after fix
pnpm vitest run packages/ui/src/molecules/CarouselCard/CarouselCard.test.tsx
