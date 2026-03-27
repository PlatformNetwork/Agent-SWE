# Garrett-s-Apps/nexus-31 (original PR)

Garrett-s-Apps/nexus (#31): fix: Eliminate CLI session timeouts for long-running autonomous work

## Summary
- Docker `--read-only` prevented Claude CLI from writing state files → silent hang with 0 output. Added `--tmpfs` for `~/.claude`
- Docker model defaulted to `opus` (entrypoint) while native used `sonnet`. Now passes `NEXUS_CLI_MODEL=sonnet` explicitly
- STALL_TIMEOUT increased from 900s (15min) to 7200s (2hr) — sessions can now run for weeks with periodic output
- Listener hardcoded "15 minutes" message → now uses actual `STALL_TIMEOUT` value
- `safe_node` graph wrapper timeout increased from 300s (5min) to 7200s (2hr)

## Test plan
- [ ] Send a Slack message that triggers a CLI session
- [ ] Verify Docker container starts and produces stream-json output (no 0-tool hangs)
- [ ] Verify long-running tasks don't get killed prematurely
- [ ] Verify timeout message shows correct duration if stall occurs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
