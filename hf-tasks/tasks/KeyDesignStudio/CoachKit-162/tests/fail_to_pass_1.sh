#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd apps/web && npx vitest run modules/ai-plan-builder/tests/ai-plan-builder.constraint-guardrails.unit.test.ts modules/ai-plan-builder/tests/workout-detail-renderer.explainability.unit.test.ts
