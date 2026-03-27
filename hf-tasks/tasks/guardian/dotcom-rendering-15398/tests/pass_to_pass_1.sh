#!/bin/bash
# This test must PASS on base commit AND after fix
cd dotcom-rendering && pnpm test -- src/components/FootballMatchList.test.tsx
