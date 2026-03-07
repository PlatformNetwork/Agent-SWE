#!/bin/bash
# This test must FAIL on base commit, PASS after fix
go test ./internal/controller/resourcemanager -run TestPersonalOrganizationReconcileCreatesProject -count=1
