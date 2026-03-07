#!/bin/bash
# This test must PASS on base commit AND after fix
chmod +x gradlew && ./gradlew :apps:core-api:compileJava
