import { describe, expect, it } from 'vitest';

import { validateDraftPlanAgainstSetup } from '@/modules/ai-plan-builder/rules/constraint-validator';
import type { DraftPlanV1, DraftPlanSetupV1 } from '@/modules/ai-plan-builder/rules/draft-generator';

function buildSetup(overrides: Partial<DraftPlanSetupV1> = {}): DraftPlanSetupV1 {
  return {
    weekStart: 'monday',
    startDate: '2026-01-05',
    eventDate: '2026-04-05',
    weeksToEvent: 12,
    weeklyAvailabilityDays: [0, 1, 2, 3, 4, 5, 6],
    weeklyAvailabilityMinutes: 0,
    disciplineEmphasis: 'balanced',
    riskTolerance: 'med',
    maxIntensityDaysPerWeek: 3,
    maxDoublesPerWeek: 1,
    longSessionDay: 6,
    coachGuidanceText: 'Experienced athlete ready for volume.',
    ...overrides,
  };
}

function buildDraft(sessions: DraftPlanV1['weeks'][number]['sessions'], setupOverrides: Partial<DraftPlanSetupV1> = {}) {
  return {
    version: 'v1',
    setup: buildSetup(setupOverrides),
    weeks: [{ weekIndex: 0, locked: false, sessions }],
  } satisfies DraftPlanV1;
}

describe('constraint-validator guardrails', () => {
  it('flags consecutive intensity days', () => {
    const draft = buildDraft([
      { weekIndex: 0, ordinal: 0, dayOfWeek: 2, discipline: 'run', type: 'tempo', durationMinutes: 50, locked: false },
      { weekIndex: 0, ordinal: 1, dayOfWeek: 3, discipline: 'bike', type: 'threshold', durationMinutes: 55, locked: false },
      { weekIndex: 0, ordinal: 2, dayOfWeek: 5, discipline: 'swim', type: 'endurance', durationMinutes: 40, locked: false },
    ]);

    const violations = validateDraftPlanAgainstSetup({ setup: draft.setup, draft });
    expect(violations.some((v) => v.code === ('CONSECUTIVE_INTENSITY_DAYS' as any))).toBe(true);
  });

  it('flags long session followed by intensity', () => {
    const draft = buildDraft([
      {
        weekIndex: 0,
        ordinal: 0,
        dayOfWeek: 5,
        discipline: 'run',
        type: 'endurance',
        durationMinutes: 90,
        notes: 'Long run progression',
        locked: false,
      },
      {
        weekIndex: 0,
        ordinal: 1,
        dayOfWeek: 6,
        discipline: 'bike',
        type: 'threshold',
        durationMinutes: 60,
        locked: false,
      },
    ]);

    const violations = validateDraftPlanAgainstSetup({ setup: draft.setup, draft });
    expect(violations.some((v) => v.code === ('LONG_SESSION_FOLLOWED_BY_INTENSITY' as any))).toBe(true);
  });

  it('enforces key session count bounds', () => {
    const draft = buildDraft([
      {
        weekIndex: 0,
        ordinal: 0,
        dayOfWeek: 1,
        discipline: 'run',
        type: 'endurance',
        durationMinutes: 50,
        notes: 'Key session aerobic focus',
        locked: false,
      },
      {
        weekIndex: 0,
        ordinal: 1,
        dayOfWeek: 3,
        discipline: 'bike',
        type: 'endurance',
        durationMinutes: 70,
        notes: 'Long ride steady',
        locked: false,
      },
      {
        weekIndex: 0,
        ordinal: 2,
        dayOfWeek: 5,
        discipline: 'run',
        type: 'endurance',
        durationMinutes: 45,
        notes: 'Key session hills',
        locked: false,
      },
      {
        weekIndex: 0,
        ordinal: 3,
        dayOfWeek: 0,
        discipline: 'bike',
        type: 'endurance',
        durationMinutes: 65,
        notes: 'Brick simulation',
        locked: false,
      },
    ]);

    const violations = validateDraftPlanAgainstSetup({ setup: draft.setup, draft });
    expect(violations.some((v) => v.code === ('KEY_SESSION_COUNT_OUT_OF_BOUNDS' as any))).toBe(true);
  });
});
