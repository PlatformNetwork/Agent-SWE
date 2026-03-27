# NixeloApp/cascade-391 (original PR)

NixeloApp/cascade (#391): 🧬 Refactor: Consolidate fast-path user stats counting logic

- Extracted `countByProjectParallel` helper function in `convex/users.ts`.
- Updated `countIssuesByReporterFast` to use the helper.
- Updated `countIssuesByAssigneeFast` to use the helper.
- Created `.jules/refactor.md` to track refactoring decisions.

---
*PR created automatically by Jules for task [7965587190447787532](https://jules.google.com/task/7965587190447787532) started by @mikestepanov*
