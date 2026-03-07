#!/bin/bash
# This test must FAIL on base commit, PASS after fix
bash -lc 'source $HOME/.cargo/env && cargo test -p polars-arrow --features compute --test compute_feature_flags'
