#!/bin/bash
# This test must PASS on base commit AND after fix
mvn -q -f sites/bunia/pom.xml help:evaluate -Dexpression=project.version -DforceStdout
