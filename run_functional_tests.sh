#!/bin/bash
set -e

# Automatically discover all test directories in replay/
# Sort them to ensure consistent test order
tests=()
while IFS= read -r -d '' dir; do
    test_name=$(basename "$dir")
    tests+=("$test_name")
done < <(find replay -maxdepth 1 -type d -not -path replay -print0 | sort -z)

echo "Found ${#tests[@]} functional tests"

for test in "${tests[@]}"; do
    echo "====================================================================="
    echo "Running test: $test"
    echo "====================================================================="
    ./functional_test.py replay "$test"
done

echo "All functional tests passed!"

