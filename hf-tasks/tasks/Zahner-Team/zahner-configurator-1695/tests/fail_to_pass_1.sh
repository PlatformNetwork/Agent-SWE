#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- --run tests/materials/atlasRotationRepeat.test.ts
