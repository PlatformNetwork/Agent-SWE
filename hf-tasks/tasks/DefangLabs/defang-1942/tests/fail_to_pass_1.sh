#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd src && go test ./pkg/cli/client/byoc -run TestProjectUpdateIncludesEtag -count=1
