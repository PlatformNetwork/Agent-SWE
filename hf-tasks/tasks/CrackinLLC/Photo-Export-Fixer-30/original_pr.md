# CrackinLLC/Photo-Export-Fixer-30 (original PR)

CrackinLLC/Photo-Export-Fixer (#30): T-00063: GUI polish — scope mousewheel, async startup check, clamp progress, XDG config

## Summary

- Scope mousewheel binding to scrollable area only (enter/leave events) instead of global bind_all — fixes I-00022
- Move ExifTool startup check to background thread so UI appears immediately — fixes I-00023
- Clamp progress percentage to 100% max — fixes I-00024
- Respect XDG_CONFIG_HOME on Linux for settings file location — fixes I-00025

## Test plan

- Added 7 new tests in `pef/tests/test_gui.py` covering XDG_CONFIG_HOME behavior (3 tests) and progress clamping logic (4 tests)
- `den submit` pipeline: all tests pass, clean check

## Scope

- In scope: 4 independent GUI polish fixes as specified in T-00063
- Out of scope: no other GUI changes

## Risk surfaces

- Security: no
- Authorization: no
- Data integrity: no
- External integrations: no
- CI: no

## Artifacts

- Task: forgecrew-work/tasks/T-00063__WS-000002__TASK__gui-polish-scope-mousewheel-async-startup-check-cl.md
