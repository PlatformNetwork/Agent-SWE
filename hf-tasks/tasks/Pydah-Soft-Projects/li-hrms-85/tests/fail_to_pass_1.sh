#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd /repo/backend && npm test -- --runTestsByPath tests/attendance/recalculateOnAttendanceUpdate.test.js
