# block/cachew-131 (original PR)

block/cachew (#131): feat: integrate git maintenance for mirror repos

## Summary
- Adds `registerMaintenance()` to configure `maintenance.strategy=incremental` and run `git maintenance register` for each mirror repo
- Calls it after clone (`executeClone`) and on startup discovery (`DiscoverExisting`)
- Runs `git maintenance start` once in `NewManager()` to set up system-level scheduling (launchd/systemd)
- Adds `Maintenance` config flag (default `false`) to gate all maintenance behavior, keeping tests clean

Closes #125

## Test plan
- [ ] Manually verify `git config --get maintenance.strategy` returns `incremental` after clone
- [ ] Verify `git config --global --get-all maintenance.repo` includes the mirror path
- [ ] Verify system scheduler is registered (`launchctl list | grep git` on macOS)
- [ ] Existing tests pass without pollution (maintenance disabled by default)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
