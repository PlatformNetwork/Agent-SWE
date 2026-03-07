# CrackinLLC/Photo-Export-Fixer-15 (original PR)

CrackinLLC/Photo-Export-Fixer (#15): T-00034: Wire cancel button into preview/dry_run path

## Summary

- Wire the cancel button to work during preview (dry_run) mode — previously it was non-functional because `_on_dry_run()` never created `self._cancel_event`
- Add `cancel_event` parameter to `orchestrator.dry_run()` with checks at each iteration in the JSON processing loop
- Show context-appropriate cancel confirmation dialog ("Cancel Preview" vs "Cancel Processing")
- Handle cancelled dry_run by showing "Preview cancelled" status and returning to setup view

## Test plan

- `den submit` pipeline: all existing tests pass (dry_run tests call without cancel_event, which defaults to None — backward compatible)
- Existing `test_orchestrator.py` dry_run tests verify no regression
- Manual verification: click Preview on a collection, click Cancel → preview stops, GUI returns to setup view with "Preview cancelled" status
- Manual verification: click Cancel during preview, choose "No" → preview continues
- Manual verification: process cancel still works (no regression)

## Scope

- In scope: `pef/gui/main_window.py` (`_on_dry_run`, `_on_cancel`), `pef/core/orchestrator.py` (`dry_run`), `pef/core/models.py` (`DryRunResult.cancelled`)
- Out of scope: Process path cancellation (already works)

## Risk surfaces

- Security: no
- Authorization: no
- Data integrity: no (dry_run is read-only, cancellation just returns early)
- External integrations: no
- CI: no

## Artifacts

- Task: forgecrew-work/tasks/T-00034__WS-000002__TASK__wire-cancel-button-into-preview-dry-run-path.md
