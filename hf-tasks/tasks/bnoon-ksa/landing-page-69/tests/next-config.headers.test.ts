import { describe, it, expect } from "vitest";

async function loadNextConfig() {
  const module = await import("../next.config.js");
  return (module as { default?: unknown }).default ?? module;
}

describe("next.config headers", () => {
  it("adds cache-control headers for images, static assets, and health API", async () => {
    const nextConfig = (await loadNextConfig()) as {
      headers?: () => Promise<
        { source: string; headers: { key: string; value: string }[] }[]
      >;
    };

    const headers = await nextConfig.headers?.();
    expect(headers).toBeDefined();

    const imageHeader = headers?.find((entry) => entry.source === "/images/:path*");
    const staticHeader = headers?.find(
      (entry) => entry.source === "/_next/static/:path*"
    );
    const healthHeader = headers?.find((entry) => entry.source === "/api/health");

    expect(imageHeader?.headers).toContainEqual({
      key: "Cache-Control",
      value: "public, max-age=2592000, immutable",
    });
    expect(staticHeader?.headers).toContainEqual({
      key: "Cache-Control",
      value: "public, max-age=31536000, immutable",
    });
    expect(healthHeader?.headers).toContainEqual({
      key: "Cache-Control",
      value: "no-cache, no-store, must-revalidate",
    });
  });
});
