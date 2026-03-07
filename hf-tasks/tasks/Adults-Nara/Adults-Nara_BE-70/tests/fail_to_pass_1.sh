#!/bin/bash
# This test must FAIL on base commit, PASS after fix
chmod +x gradlew && ./gradlew :apps:core-api:test --tests com.ott.core.modules.preference.service.UserPreferenceServiceTest
