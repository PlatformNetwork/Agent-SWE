#!/bin/bash
# This test must PASS on base commit AND after fix
cd src && go test ./pkg/cli/client/byoc/aws -run TestDomainMultipleProjectSupport -count=1
