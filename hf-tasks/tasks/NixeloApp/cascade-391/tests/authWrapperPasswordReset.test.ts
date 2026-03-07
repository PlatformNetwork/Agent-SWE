import { beforeEach, describe, expect, it, vi } from "vitest";
import { performPasswordResetHandler } from "./authWrapper";
import { logger } from "./lib/logger";

vi.mock("./lib/logger", () => ({
  logger: {
    error: vi.fn(),
  },
}));

vi.mock("./lib/env", () => ({
  getConvexSiteUrl: () => "https://auth.example.test",
}));

describe("performPasswordResetHandler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends password reset request without logging on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    global.fetch = fetchMock as typeof fetch;

    await expect(
      performPasswordResetHandler({} as any, { email: "reset-user@domain.test" }),
    ).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("https://auth.example.test/api/auth/signin/password");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toEqual({
      "Content-Type": "application/x-www-form-urlencoded",
    });

    const params = new URLSearchParams(options?.body as string);
    expect(params.get("email")).toBe("reset-user@domain.test");
    expect(params.get("flow")).toBe("reset");
    expect(logger.error).not.toHaveBeenCalled();
  });

  it("logs an error when the auth endpoint responds with a failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: () => Promise.resolve("Bad Gateway"),
    });
    global.fetch = fetchMock as typeof fetch;

    await expect(
      performPasswordResetHandler({} as any, { email: "no-such-user@domain.test" }),
    ).resolves.toBeUndefined();

    expect(logger.error).toHaveBeenCalledTimes(1);
    const [message, payload] = (logger.error as any).mock.calls[0];
    expect(message).toBe("Password reset request failed");
    expect(payload.error).toBeInstanceOf(Error);
    expect(payload.error.message).toContain("502");
    expect(payload.error.message).toContain("Bad Gateway");
  });

  it("logs an error when the request itself throws", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    global.fetch = fetchMock as typeof fetch;

    await expect(
      performPasswordResetHandler({} as any, { email: "timeout@domain.test" }),
    ).resolves.toBeUndefined();

    expect(logger.error).toHaveBeenCalledTimes(1);
    const [message, payload] = (logger.error as any).mock.calls[0];
    expect(message).toBe("Password reset request failed");
    expect(payload.error).toBeInstanceOf(Error);
    expect(payload.error.message).toBe("network down");
  });
});
