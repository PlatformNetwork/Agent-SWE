#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd dotcom-rendering && pnpm test -- src/components/FootballMatchHeader/FootballMatchHeader.test.tsx
