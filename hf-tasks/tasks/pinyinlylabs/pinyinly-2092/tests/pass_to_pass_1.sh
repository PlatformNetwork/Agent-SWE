#!/bin/bash
# This test must PASS on base commit AND after fix
yarn workspace @pinyinly/app vitest run test/client/ui/IconImage.test.ts
