#!/bin/bash
# This test must FAIL on base commit, PASS after fix
go test ./api -tags=small -run "TestHandleMetadataTriage_InvalidURL"
