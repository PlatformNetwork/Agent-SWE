#!/bin/bash
# This test must PASS on base commit AND after fix
npm test -- --run tests/materials/atlasTiling.test.ts
