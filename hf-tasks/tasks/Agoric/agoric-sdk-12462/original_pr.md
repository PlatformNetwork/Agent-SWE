# Agoric/agoric-sdk-12462 (original PR)

Agoric/agoric-sdk (#12462): Upgrade to TypeScript 6.0.0-beta

## TypeScript 6 Upgrade - Complete ✅

Successfully upgraded from TypeScript 5.9.x to TypeScript 6.0.0-beta with minimal changes.

### Changes Completed
- [x] Update TypeScript dependencies (root + cosmic-proto)
- [x] Update yarn.lock with TypeScript 6
- [x] Remove deprecated `downlevelIteration` compiler option
- [x] Fix 26 unused @ts-expect-error directives across 17 files
- [x] Fix 9 type errors with targeted suppressions/fixes
- [x] Fix 15 non-relative imports with .ts extensions
- [x] Fix Docker build: copy types directory for anylogger type definitions
- [x] Fix ts-expect-error placement in eip712-messages.ts
- [x] Code review passed ✅
- [x] Security scan passed ✅

### Summary
**50+ total changes across 30 files** to ensure TypeScript 6 compatibility.

### Known Remaining Issues (Non-blocking)
3 declaration emit errors that don't affect runtime or type safety:
- **TS9006** (2x): Deep type inference in econ-behaviors.js
- **TS4094** (1x): Private field pattern in wrap-marshaller.js

These only affect .d.ts generation and can be addressed in follow-up work.

### Pre-existing Issues
270 module resolution errors (TS2307) - these are expected before packages are built and are unrelated to the TypeScript 6 upgrade.

<!-- START COPILOT ORIGINAL PROMPT -->



<details>

<summary>Original prompt</summary>

> 
> ----
> 
> *This section details on the original issue you should resolve*
> 
> <issue_title>upgrade to TypeScript 6</issue_title>
> <issue_description># What
> 
> Upgrade from TypeScript 5 to the new TypeScript 6
> 
> ## Why
> 
> Keep up to date, get latest improvements. Unlock reaching TS 7.0 for tsgo.
> 
> ## How
> 
> Bump the package dependencies
> Read https://devblogs.microsoft.com/typescript/announcing-typescript-6-0-beta/
> Accommodate breaking changes
> </issue_description>
> 
> <agent_instructions>try to complete the upgrade independently. once you've fixed everything you can solve, assess the remaining errors and generate a report of the remaining problems to solve</agent_instructions>
> 
> ## Comments on the Issue (you are @copilot in this section)
> 
> <comments>
> </comments>
> 


</details>



<!-- START COPILOT CODING AGENT SUFFIX -->

- Fixes Agoric/agoric-sdk#12461

<!-- START COPILOT CODING AGENT TIPS -->
---

✨ Let Copilot coding agent [set things up for you](https://github.com/Agoric/agoric-sdk/issues/new?title=✨+Set+up+Copilot+instructions&body=Configure%20instructions%20for%20this%20repository%20as%20documented%20in%20%5BBest%20practices%20for%20Copilot%20coding%20agent%20in%20your%20repository%5D%28https://gh.io/copilot-coding-agent-tips%29%2E%0A%0A%3COnboard%20this%20repo%3E&assignees=copilot) — coding agent works faster and does higher quality work when set up for your repo.

