#!/bin/bash
# This test must PASS on base commit AND after fix
npx tsc -p libs/ui/tsconfig.lib.json --noEmit
