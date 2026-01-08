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
    echo "Running test: $test at $(date)"
    echo "====================================================================="
    start_time=$(date +%s)
    ./functional_test.py replay "$test"
    end_time=$(date +%s)
    echo "Test $test took $((end_time - start_time)) seconds"
done

echo "All functional tests passed!"

