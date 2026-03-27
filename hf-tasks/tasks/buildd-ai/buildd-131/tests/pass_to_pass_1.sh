#!/bin/bash
# This test must PASS on base commit AND after fix
source /root/.bashrc && bun test apps/local-ui/__tests__/unit/workers.test.ts
