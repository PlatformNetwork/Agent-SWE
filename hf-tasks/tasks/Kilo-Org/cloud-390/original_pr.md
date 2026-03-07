# Kilo-Org/cloud-390 (original PR)

Kilo-Org/cloud (#390): App Builder - Extract shared git protocol utils and fix byte-length bug

## Summary
- Extract duplicated `resolveHeadSymref` and `formatPacketLine` into a shared `git-protocol-utils.ts` module, removing identical copies from `git-clone-service.ts`, `git-receive-pack-service.ts`, and `handlers/git-protocol.ts`
- Add `symref=HEAD:<branch>` capability advertisement to both upload-pack and receive-pack `info/refs` responses, so git clients can detect the default branch on clone/push
- Fix `formatPacketLine` in `handlers/git-protocol.ts` which was using JS string length instead of UTF-8 byte length for the pkt-line hex prefix (incorrect for multi-byte characters)

## Changes
- **New:** `cloudflare-app-builder/src/git/git-protocol-utils.ts` — shared module with `resolveHeadSymref` and `formatPacketLine` (hoisted `TextEncoder`)
- **New:** `cloudflare-app-builder/src/git/git-protocol-utils.test.ts` — unit tests for `formatPacketLine` including a multi-byte UTF-8 test that catches the string-length bug
- **New:** `cloudflare-app-builder/src/git/git-clone-service.test.ts` — integration tests for `handleInfoRefs` symref advertisement and pkt-line correctness
- **Modified:** `git-clone-service.ts`, `git-receive-pack-service.ts` — import shared functions, remove private static duplicates, add symref capability
- **Modified:** `handlers/git-protocol.ts` — replace buggy local `formatPacketLine` with shared import
