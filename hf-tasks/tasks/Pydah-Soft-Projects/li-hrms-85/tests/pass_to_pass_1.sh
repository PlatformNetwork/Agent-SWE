#!/bin/bash
# This test must PASS on base commit AND after fix
cd /repo/backend && npm test -- --runTestsByPath tests/api/sanity.test.js
