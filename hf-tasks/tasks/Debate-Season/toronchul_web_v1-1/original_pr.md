# Debate-Season/toronchul_web_v1-1 (original PR)

Debate-Season/toronchul_web_v1 (#1): feat: add TDS typography system with Pretendard web font

- Import Pretendard Variable font via CDN (jsdelivr)
- Add all TDS font size tokens from de_fonts.dart: largest (48px), header-28/24/20/18, body-16/14, caption-12/12-tight
- Each token includes font-size, line-height, letter-spacing (-2.5%)
- Set body defaults: Pretendard font, grey-120 background, grey-10 text to match the Flutter app's dark theme
- Update tailwind.config.ts with matching fontSize extend entries
- Simplify layout.tsx: remove Google Fonts, add Korean locale

https://claude.ai/code/session_01E8KTvstfyeZbk6NU6PGj1h
