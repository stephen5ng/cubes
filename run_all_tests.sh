#!/bin/bash
set -e

# Save current directory for relative paths
REPO_ROOT="$(pwd)"

# Add current directory and src to Python path (matching runpygame.sh)
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}/../easing-functions:${REPO_ROOT}/../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH"

# Set environment variables for tests that need them
export RGBME_SUPPRESS_ADAPTER_LOAD_ERRORS=1

# Helper for section headers
print_header() {
    echo ""
    echo "====================================================================="
    echo "$1"
    echo "====================================================================="
}

# 1. Unit Tests
print_header "Running UNIT Tests (tests/unit/ and tests/test_*.py)"
# We run tests/test_*.py (root tests) and tests/unit/
# Using -v for visibility, feel free to remove
python3 -m pytest tests/unit/ tests/test_*.py

# 2. Integration Tests
print_header "Running INTEGRATION Tests (tests/integration/)"
python3 -m pytest tests/integration/

# 3. E2E Tests
print_header "Running E2E Tests (tests/e2e/)"
python3 -m pytest tests/e2e/

# 4. Functional Tests
print_header "Running FUNCTIONAL Tests (./run_functional_tests.sh)"
./run_functional_tests.sh

echo ""
echo "All tests passed successfully!"
