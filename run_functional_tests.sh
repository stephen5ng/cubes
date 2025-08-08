#!/bin/bash
set -e

tests=(
    2player
    gamepad
    sng
    stress_0.01
    stress_0.1
)

for test in "${tests[@]}"; do
    echo "====================================================================="
    echo "Running test: $test"
    echo "====================================================================="
    ./functional_test.py replay "$test"
done

echo "All functional tests passed!"

