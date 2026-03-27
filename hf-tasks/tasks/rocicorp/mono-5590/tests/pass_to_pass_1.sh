#!/bin/bash
# This test must PASS on base commit AND after fix
npm test -- --project zero-cache/no-pg packages/zero-cache/src/services/change-source/pg/lsn.test.ts
