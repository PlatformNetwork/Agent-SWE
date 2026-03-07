#!/bin/bash
# This test must FAIL on base commit, PASS after fix
mvn -q -Dmaven.test.skip=true package && javac -cp target/jt400-21.0.6-dev.jar -d target/test-classes src/test/java/VirtualThreadsTest.java src/test/java/VirtualThreadsDataSourceTest.java src/test/java/VirtualThreadsManagedDataSourceTest.java && java -cp target/jt400-21.0.6-dev.jar:target/test-classes VirtualThreadsManagedDataSourceTest
