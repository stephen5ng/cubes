#!/bin/bash
set -e

# Save current directory for relative paths
REPO_ROOT="$(pwd)"

# Add current directory and src to Python path (matching runpygame.sh)
# Use absolute paths since we'll cd into tests/
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}/../easing-functions:${REPO_ROOT}/../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH"

# Set environment variables for tests that need them
export RGBME_SUPPRESS_ADAPTER_LOAD_ERRORS=1

# Run tests with pytest for better compatibility
echo "Running unit tests with pytest..."
echo

# Run pytest on test files in the tests directory (excluding e2e and integration subdirs)
# Pass any additional arguments to pytest (e.g., -v for verbose, -k for filtering)
python3 -m pytest tests/test_*.py "$@"
