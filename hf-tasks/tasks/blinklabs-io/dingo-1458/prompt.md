# blinklabs-io/dingo-1458

Implement ChainSync so blocks are processed and committed one-by-one and downstream peers see new data immediately, avoiding idle timeouts.

Add robust fork handling: clear stale header state on mismatches, track consecutive mismatches, and trigger an automatic resync after a small threshold. Provide hooks to reset connection state when a resync or connection switch occurs.

Correct Praos epoch nonce behavior: use the genesis nonce when the stability window crosses an epoch boundary, then combine with the last block hash of the previous epoch; return no nonce if the requested epoch is ahead. Suppress epoch events until near the upstream tip.

During initial sync, gate VRF/KES verification on availability of epoch data and treat verification failures as non-fatal when significantly behind the tip.
