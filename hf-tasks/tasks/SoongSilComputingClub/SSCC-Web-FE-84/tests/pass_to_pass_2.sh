#!/bin/bash
# This test must PASS on base commit AND after fix
npm test -- --run src/shared/auth/require-admin.test.tsx
