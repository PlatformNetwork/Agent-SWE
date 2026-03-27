import { describe, it, expect, vi, afterEach } from 'vitest';

import * as authApi from '@mohang/ui';
import { publicApi } from '@mohang/ui';

describe('signupAuthCodeCheck logging', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not log the auth code payload when verifying', async () => {
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const postSpy = vi
      .spyOn(publicApi, 'post')
      .mockResolvedValue({
        data: { message: 'ok', statusCode: 200 },
      } as any);

    const payload = { email: 'debugger@example.com', otp: '321654' };

    const response = await authApi.signupAuthCodeCheck(payload);

    expect(response).toEqual({ message: 'ok', statusCode: 200 });
    expect(postSpy).toHaveBeenCalledWith(
      '/api/v1/auth/email/otp/verify',
      payload,
    );
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('forwards API error details without logging payloads', async () => {
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const error = {
      response: {
        status: 400,
        data: { message: 'invalid code' },
      },
    };
    vi.spyOn(publicApi, 'post').mockRejectedValue(error as any);

    const payload = { email: 'auditor@example.com', otp: '998877' };

    await expect(authApi.signupAuthCodeCheck(payload)).rejects.toEqual({
      message: 'invalid code',
      statusCode: 400,
    });
    expect(logSpy).not.toHaveBeenCalled();
  });
});
