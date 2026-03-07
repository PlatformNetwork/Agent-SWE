#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- --run src/shared/lib/use-activity-gallery.test.tsx
