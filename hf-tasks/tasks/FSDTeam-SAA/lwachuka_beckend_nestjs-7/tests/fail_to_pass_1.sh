#!/bin/bash
# This test must FAIL on base commit, PASS after fix
npm test -- src/app.controller.spec.ts
