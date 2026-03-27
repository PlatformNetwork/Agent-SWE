import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ROLES, STORAGE_KEYS } from '@/shared/auth/jwt';

vi.mock('@/shared/lib/recruitment', () => ({
  getApplicationPhase: vi.fn(() => 'closed'),
}));

vi.mock('@/shared/auth/use-auth', () => ({
  useAuth: () => ({
    isLoggedIn: true,
    accessToken: sessionStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN),
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

import HeroSection from './hero-section';

function base64UrlEncode(obj: unknown) {
  const json = JSON.stringify(obj);
  const b64 = btoa(unescape(encodeURIComponent(json)));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function createMockJwt(payload: Record<string, unknown>) {
  const header = { alg: 'HS256', typ: 'JWT' };
  return `${base64UrlEncode(header)}.${base64UrlEncode(payload)}.signature`;
}

describe('HeroSection admin CTA override', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    sessionStorage.clear();
  });

  it('shows application CTA for admin even when phase is closed', () => {
    const token = createMockJwt({ role: ROLES.ADMIN, exp: Math.floor(Date.now() / 1000) + 60 });
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);

    render(
      <MemoryRouter>
        <HeroSection hasApplication={false} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: '신청서 작성하기' })).toBeTruthy();
  });

  it('keeps closed message without CTA for non-admin users', () => {
    const token = createMockJwt({ role: ROLES.USER, exp: Math.floor(Date.now() / 1000) + 60 });
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);

    render(
      <MemoryRouter>
        <HeroSection hasApplication={false} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('link', { name: '신청서 작성하기' })).toBeNull();
    expect(screen.getByText('지금은 SSCC 신청 기간이')).toBeTruthy();
  });
});
