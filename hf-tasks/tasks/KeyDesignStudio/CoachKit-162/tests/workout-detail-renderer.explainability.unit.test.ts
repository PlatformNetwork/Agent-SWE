import { describe, expect, it } from 'vitest';

import { renderWorkoutDetailFromSessionDetailV1 } from '@/lib/workoutDetailRenderer';

const baseDetail = {
  objective: 'Easy run (45 min)',
  structure: [
    { blockType: 'warmup', durationMinutes: 10, steps: 'Easy jog.' },
    { blockType: 'main', durationMinutes: 25, steps: 'Comfortable steady effort.' },
    { blockType: 'cooldown', durationMinutes: 10, steps: 'Relaxed finish.' },
  ],
  targets: { primaryMetric: 'RPE', notes: 'Stay relaxed.' },
};

describe('workout detail rendering explainability', () => {
  it('renders purpose and explainability blocks with spacing', () => {
    const detail = {
      ...baseDetail,
      purpose: 'Reset legs after travel.',
      explainability: {
        whyThis: 'Build aerobic durability.',
        whyToday: 'Fits between harder days.',
        ifMissed: 'Replace with short walk.',
        ifCooked: 'Swap for recovery spin.',
      },
    } as any;

    const rendered = renderWorkoutDetailFromSessionDetailV1(detail as any);
    expect(rendered).toBe(
      [
        'Easy run',
        'Reset legs after travel.',
        '',
        'WARMUP: 10 min – Easy jog.',
        'MAIN: 25 min – Comfortable steady effort.',
        'COOLDOWN: 10 min – Relaxed finish.',
        '',
        'WHY THIS: Build aerobic durability.',
        'WHY TODAY: Fits between harder days.',
        'IF MISSED: Replace with short walk.',
        'IF COOKED: Swap for recovery spin.',
      ].join('\n')
    );
  });

  it('omits empty purpose and explainability sections', () => {
    const detail = {
      ...baseDetail,
      purpose: '   ',
      explainability: {
        whyThis: '  ',
        whyToday: '',
      },
    } as any;

    const rendered = renderWorkoutDetailFromSessionDetailV1(detail as any);
    expect(rendered).toBe(
      [
        'Easy run',
        '',
        'WARMUP: 10 min – Easy jog.',
        'MAIN: 25 min – Comfortable steady effort.',
        'COOLDOWN: 10 min – Relaxed finish.',
      ].join('\n')
    );
  });
});
