#!/bin/bash
# This test must FAIL on base commit, PASS after fix
cd /repo/donotlate_project && chmod +x gradlew && ./gradlew test --tests com.late.donot.calculator.controller.CalculatorPushSaveControllerTest
