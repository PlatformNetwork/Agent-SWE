#!/bin/bash
# This test must PASS on base commit AND after fix
mvn -q -Dmaven.test.skip=true package
