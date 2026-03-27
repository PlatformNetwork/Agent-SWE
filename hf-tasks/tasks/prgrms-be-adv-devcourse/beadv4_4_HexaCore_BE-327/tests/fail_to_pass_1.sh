#!/bin/bash
# This test must FAIL on base commit, PASS after fix
./gradlew :cash:test --tests com.back.cash.CashPaymentApiInterfaceExposureTest
