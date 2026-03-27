#!/bin/bash
# This test must PASS on base commit AND after fix
npx mocha -r ts-node/register 'test/webhook.test.ts'
