#!/bin/bash
# This test must PASS on base commit AND after fix
./gradlew :cash:test --tests com.back.cash.TossPaymentsClientTest
