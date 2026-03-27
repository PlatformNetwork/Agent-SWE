import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
import HeroBanner from "./HeroBanner";
import HeroBannerAr from "../ar/HomeDemo2/HeroBanner";

const CDN_BASE =
  "https://bnoonsa-bjftd5h4a7bae0ce.z02.azurefd.net/website/videos/";

function getFetchableVideoSources(container: HTMLElement) {
  const videos = Array.from(container.querySelectorAll("video"));
  return videos
    .map((video) => {
      const preload = video.getAttribute("preload");
      const source = video.querySelector("source");
      const src = source?.getAttribute("src") || "";
      const isFetchable = src.trim().length > 0 && preload !== "none";
      return { src, isFetchable };
    })
    .filter((entry) => entry.isFetchable)
    .map((entry) => entry.src);
}

describe("HeroBanner video lazy loading", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("loads only current and next English banner videos from the CDN", () => {
    const { container } = render(<HeroBanner />);
    const videoSources = getFetchableVideoSources(container);

    expect(videoSources).toHaveLength(2);
    expect(videoSources.every((src) => src.startsWith(CDN_BASE))).toBe(true);
  });

  it("loads only current and next Arabic banner videos from the CDN", () => {
    const { container } = render(<HeroBannerAr />);
    const videoSources = getFetchableVideoSources(container);

    expect(videoSources).toHaveLength(2);
    expect(videoSources.every((src) => src.startsWith(CDN_BASE))).toBe(true);
  });
});
