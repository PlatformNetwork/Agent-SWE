#!/bin/bash
# This test must PASS on base commit AND after fix
cd /repo/donotlate_project && chmod +x gradlew && ./gradlew assemble
