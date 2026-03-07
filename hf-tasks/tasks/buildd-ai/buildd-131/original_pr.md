# buildd-ai/buildd-131 (original PR)

buildd-ai/buildd (#131): test: add session resume integration test with diagnostics

## Summary
- Adds `integration-session-resume.test.ts` — a focused integration test for the session resume pipeline
- Agent creates a file + commit, completes, then receives a follow-up message asking about context from the first session
- Verifies the marker/secret code is preserved across sessions (context continuity)
- On failure, dumps rich diagnostics: sessionId, resume layer used (SDK resume vs reconstruction vs text-only), milestones, session logs, and output

## Test design

**Phase 1** — Agent creates commit with marker file and remembers a secret code
**Phase 2** — Capture post-completion diagnostics (sessionId, milestones, commits)
**Phase 3** — Send follow-up asking for the secret code
**Phase 4** — Verify output contains the marker; log resume layer and session log entries

Follows the same API helpers, setup/teardown, and environment guard pattern as `integration.test.ts`.

## Test plan
- [ ] Run with `BUILDD_TEST_SERVER=http://localhost:3000 bun test apps/local-ui/__tests__/integration-session-resume.test.ts`
- [ ] Verify diagnostics output on both pass and fail paths

🤖 Generated with [Claude Code](https://claude.com/claude-code)
