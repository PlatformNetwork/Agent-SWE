import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ROLES, STORAGE_KEYS } from '@/shared/auth/jwt';

vi.mock('@/shared/lib/recruitment', () => ({
  isApplicationOpen: vi.fn(() => false),
}));

import SubmitSection from './submit-section';

function base64UrlEncode(obj: unknown) {
  const json = JSON.stringify(obj);
  const b64 = btoa(unescape(encodeURIComponent(json)));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function createMockJwt(payload: Record<string, unknown>) {
  const header = { alg: 'HS256', typ: 'JWT' };
  return `${base64UrlEncode(header)}.${base64UrlEncode(payload)}.signature`;
}

describe('SubmitSection admin override', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('admin token keeps submit button enabled even when application is closed', () => {
    const token = createMockJwt({ role: ROLES.ADMIN, exp: Math.floor(Date.now() / 1000) + 60 });
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);

    render(<SubmitSection />);

    const buttons = screen.getAllByRole('button', { name: '제출하기' });
    expect(buttons.length).toBeGreaterThan(0);
    const button = buttons[0];
    expect(button.getAttribute('aria-disabled')).toBe('false');
    expect(screen.queryByText('현재는 지원 기간이 아니에요.')).toBeNull();
  });

  it('non-admin still sees disabled state when application is closed', () => {
    const token = createMockJwt({ role: ROLES.USER, exp: Math.floor(Date.now() / 1000) + 60 });
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);

    render(<SubmitSection />);

    const buttons = screen.getAllByRole('button', { name: '제출하기' });
    expect(buttons.length).toBeGreaterThan(0);
    const button = buttons[0];
    expect(button.getAttribute('aria-disabled')).toBe('true');
    expect(screen.getAllByText('현재는 지원 기간이 아니에요.').length).toBeGreaterThan(0);
  });
});
