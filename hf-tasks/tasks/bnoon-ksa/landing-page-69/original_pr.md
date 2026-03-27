# bnoon-ksa/landing-page-69 (original PR)

bnoon-ksa/landing-page (#69): perf: CDN, cache headers, lazy-load videos, sem-rel refactor rule

## Summary

- **Azure Front Door CDN**: Created `bnoonsa-cdn` (Standard_AzureFrontDoor) profile with endpoint routing to `bnoonsa` blob storage. All video URLs now served via `bnoonsa-bjftd5h4a7bae0ce.z02.azurefd.net` for edge caching.
- **Cache-Control headers**: Added in `next.config.js` — 30-day immutable for `/images/*`, 1-year immutable for `/_next/static/*`, no-cache for `/api/health`.
- **Lazy-load banner videos**: EN and AR `HeroBanner` components now only mount the current + next slide video (2 of 6) instead of all 6. Reduces initial video load from ~167 MB to ~28 MB.
- **Semantic release**: Added `.releaserc.json` with `refactor:` → patch release rule.

## Azure Resources Created

| Resource | Type | Profile |
|----------|------|---------|
| `bnoonsa-cdn` | Front Door Standard | CDN profile |
| `bnoonsa` | Endpoint | `bnoonsa-bjftd5h4a7bae0ce.z02.azurefd.net` |
| `bnoonsa-blob` | Origin Group | → `bnoonsa.blob.core.windows.net` |

## Files Changed

- `next.config.js` — cache headers + CDN hostname in remotePatterns
- `src/components/HomeDemo2/HeroBanner.tsx` — lazy video loading + CDN URLs
- `src/components/ar/HomeDemo2/HeroBanner.tsx` — lazy video loading + CDN URLs
- `README.md` — CDN docs, updated blob storage section, resource table
- `.releaserc.json` — refactor → patch rule

## Test Plan

- [ ] Verify CDN endpoint is live: `curl -I https://bnoonsa-bjftd5h4a7bae0ce.z02.azurefd.net/website/videos/banner/banner-2.mp4`
- [ ] Verify homepage banner videos play correctly (EN + AR)
- [ ] Verify slide transitions work smoothly with lazy loading
- [ ] Verify cache headers in browser DevTools (Network tab)
- [ ] PR pipeline passes (lint, typecheck, unit tests, build, E2E)
