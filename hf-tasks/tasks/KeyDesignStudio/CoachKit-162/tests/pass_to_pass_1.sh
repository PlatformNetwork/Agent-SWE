#!/bin/bash
# This test must PASS on base commit AND after fix
cd apps/web && npx vitest run modules/ai-plan-builder/tests/ai-plan-builder.constraint-validator.unit.test.ts
