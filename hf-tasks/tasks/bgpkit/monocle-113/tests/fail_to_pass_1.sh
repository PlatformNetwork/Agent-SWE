#!/bin/bash
# This test must FAIL on base commit, PASS after fix
. $HOME/.cargo/env && cargo test --test xdg_paths -- --nocapture
