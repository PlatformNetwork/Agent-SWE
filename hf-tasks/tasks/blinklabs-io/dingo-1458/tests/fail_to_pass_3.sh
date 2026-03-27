#!/bin/bash
# This test must FAIL on base commit, PASS after fix
go test ./blockfrost -run TestSetPaginationHeadersTotals
