#!/bin/bash
# This test must PASS on base commit AND after fix
yarn workspace @agoric/internal test test/marshal.test.js
