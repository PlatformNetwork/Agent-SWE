#!/bin/bash
# This test must PASS on base commit AND after fix
go test ./api -tags=small -run TestHandleMetadataTriage_Success
