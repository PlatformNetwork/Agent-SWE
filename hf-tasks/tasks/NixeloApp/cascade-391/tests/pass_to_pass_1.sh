#!/bin/bash
# This test must PASS on base commit AND after fix
npm run test:convex:run -- convex/authWrapperRateLimit.test.ts
