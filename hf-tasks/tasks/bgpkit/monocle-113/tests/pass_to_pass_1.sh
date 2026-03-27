#!/bin/bash
# This test must PASS on base commit AND after fix
. $HOME/.cargo/env && cargo test test_ttl_durations -- --nocapture
