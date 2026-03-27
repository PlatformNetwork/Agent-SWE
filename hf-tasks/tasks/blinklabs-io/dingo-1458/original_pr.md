# blinklabs-io/dingo-1458 (original PR)

blinklabs-io/dingo (#1458): fix(chainsync): per-block processing with fork detection and epoch nonce fix



<!-- This is an auto-generated description by cubic. -->
---
## Summary by cubic
Switch to per-block ChainSync processing with commit-time iterator wakeups to keep peers responsive and prevent idle timeouts. Add persistent-fork detection with automatic re-sync and correct Praos epoch nonce; VRF/KES checks are gated and non-fatal while syncing.

- **Bug Fixes**
  - Process blocks immediately; commit per-block and notify iterators so data is visible right away and downstream peers don’t time out.
  - Clear stale headers on mismatches; track consecutive mismatches and trigger re-sync after 5 failures.
  - Fix Praos epoch nonce: use genesis when the stability window spans the epoch start, then XOR with the last block hash of the previous epoch.
  - Suppress slot-clock epoch events until near tip (95% of upstream); EpochNonce returns nil when the requested epoch is ahead.

- **New Features**
  - Added chain.NotifyIterators to wake blocked iterators after DB commits and after forging.
  - Added ChainsyncResyncFunc and ConnectionSwitchFunc; Node closes the connection and clears header dedup on fork detection or connection switch.
  - VRF/KES verification runs only when epoch data is available; failures are logged as non-fatal when >100 slots behind the upstream tip.

<sup>Written for commit a18f777d5bee595d57ab8c1bd3cb2f82f0fa62fa. Summary will update on new commits.</sup>

<!-- End of auto-generated description by cubic. -->

<!-- This is an auto-generated comment: release notes by coderabbit.ai -->
## Summary by CodeRabbit

* **New Features**
  * Added hooks to allow recovery actions and connection-state resets.
  * Enabled explicit notification of active sync iterators when a new block is committed.

* **Improvements**
  * Blocks are processed and propagated immediately to peers for faster visibility.
  * Verification during initial sync is more tolerant to improve catch-up reliability.
  * Automatic detection of header mismatches now triggers resync and clears stale state.
<!-- end of auto-generated comment: release notes by coderabbit.ai -->
