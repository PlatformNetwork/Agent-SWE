#!/bin/bash
# This test must FAIL on base commit, PASS after fix
yarn workspace @pinyinly/app vitest run test/client/ui/IconImage.size.test.tsx
