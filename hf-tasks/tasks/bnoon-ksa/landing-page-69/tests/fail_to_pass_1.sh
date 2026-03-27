#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- src/components/HomeDemo2/HeroBanner.lazyload.test.tsx
