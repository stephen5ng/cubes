#!/bin/bash
set -e

# Add current directory and src to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src"

# Set environment variables for tests that need them
export RGBME_SUPPRESS_ADAPTER_LOAD_ERRORS=1

cd tests

# List of tests to run (excluding problematic ones for now)
tests=(
    "app_test.py"
    "dictionary_test.py"
    "scorecard_test.py"
    "test_app_per_player.py"
    "test_cubes_to_game.py"
    "test_dependency_injection.py"
    "test_logging.py"
    "test_per_player_game_states.py"
    "test_replay_simple.py"
    "test_replay.py"
    "test_textrect.py"
    "test_tiles_randomness.py"
    "tiles_test.py"
)

failed_tests=()

for test in "${tests[@]}"; do
    echo "====================================================================="
    echo "Running test: $test"
    echo "====================================================================="
    
    if python3 "$test" 2>&1; then
        echo "✓ Test '$test' passed"
    else
        echo "✗ Test '$test' failed"
        failed_tests+=("$test")
    fi
    echo
done

if [ ${#failed_tests[@]} -eq 0 ]; then
    echo "All unit tests passed!"
    exit 0
else
    echo "Failed tests:"
    for test in "${failed_tests[@]}"; do
        echo "  - $test"
    done
    exit 1
fi
