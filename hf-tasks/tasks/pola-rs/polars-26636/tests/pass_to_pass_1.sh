#!/bin/bash
# This test must PASS on base commit AND after fix
bash -lc 'source $HOME/.cargo/env && cargo test -p polars-arrow --lib'
