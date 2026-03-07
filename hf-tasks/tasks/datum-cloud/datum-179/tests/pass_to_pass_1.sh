#!/bin/bash
# This test must PASS on base commit AND after fix
KUBEBUILDER_ASSETS=/repo/bin/k8s/1.32.0-linux-amd64 go test ./internal/controller/resourcemanager -run TestControllers -count=1
