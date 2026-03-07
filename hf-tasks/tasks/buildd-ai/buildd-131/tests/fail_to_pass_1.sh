#!/bin/bash
# This test must FAIL on base commit, PASS after fix
source /root/.bashrc && bun test apps/local-ui/__tests__/integration-session-resume-skip.test.ts
