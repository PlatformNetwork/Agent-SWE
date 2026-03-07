# Zahner-Team/zahner-configurator-1695 (original PR)

Zahner-Team/zahner-configurator (#1695): fix: swap face dims (not atlas) for rotateQ to prevent 12:1 skew

The previous approach swapped atlas dimensions in applyAtlasScalingForPanel when rotateQ was odd. This is wrong: the texture IMAGE is unchanged by rotation — only the UV sampling direction rotates via tex.rotation. Swapping atlas dims computes repeat values against the wrong physical dimensions (e.g. repeat.x = 108/120 = 0.9 instead of 18/240 = 0.075), causing repeat.x to sample 0.9 × 240" = 216" of atlas across 18" of panel — a 12:1 compression that produces visible skew.

The correct fix: swap the FACE dimensions to [min, max] when rotateQ is odd. After a 90° rotation, repeat.x covers mesh-V and repeat.y covers mesh-U, so:
  repeat.x = minFace / atlasWidth   (covers mesh-V after rotation)
  repeat.y = maxFace / atlasHeight   (covers mesh-U after rotation)

This produces correct physical coverage on both axes while the atlas dimensions remain un-swapped (matching the actual texture image).

https://claude.ai/code/session_01HRzerycFqxyXDWmS4TWQxQ

## Summary
Key-only materials + reload on key change.

## Changes
- Slice → key-only
- Deterministic PanelId
- New hook + Panel adapt
- Tests

## Acceptance Criteria
- [ ] AC1
- [ ] AC2
- [ ] AC3
- [ ] AC4
- [ ] AC5
- [ ] AC6

## Phase 1–8 QA Checklist
- [ ] Environment setup completed
- [ ] Smoke checks observed expected behavior
- [ ] Automated grep spot-checks recorded
- [ ] Regression sweep commands (`npm run test`, `npm run ktx:scan`) passed
- [ ] Troubleshooting log reviewed / updated if needed
- [ ] QA owner initials & date recorded: `____ / ____`

**Evidence links:** <!-- Paste permalinks to screenshots, terminal output, etc. -->

## Notes
Out of scope: exporters/HDRI.

