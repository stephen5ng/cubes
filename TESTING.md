# Testing Guide

This project includes three types of tests: Unit Tests, Integration Tests, and Functional Tests.

## Quick Start

### Run All Tests
The easiest way to ensure everything is working is to run the comprehensive test runner (if available) or run each suite individually:

```bash
./run_unit_tests.sh
python3 -m pytest tests/integration/
./run_functional_tests.sh
```

## Unit Tests

Unit tests cover individual functions and classes in isolation. They are fast and should be run frequently during development.

**Command:**
```bash
./run_unit_tests.sh
```

**Location:** `tests/test_*.py` (excluding `tests/integration/`)

## Integration Tests

Integration tests verify that components work together, typically mocking the MQTT boundary to simulate hardware but running the real game logic.

**Command:**
```bash
python3 -m pytest tests/integration/
```

**Key Features:**
- **Fast Execution**: Runs in headless mode by default.
- **Visual Mode**: Run with `--visual` to see the game window during tests.
  ```bash
  python3 -m pytest tests/integration/test_font_configuration.py --visual
  ```
- **Structure**: See `docs/testing_patterns.md` for details on writing integration tests using the `game_factory`.

## Functional Tests

Functional tests verify the end-to-end game experience by replaying recorded game sessions and comparing the output against "golden" files. These are critical for ensuring no regressions in gameplay behavior.

**Command (Run All):**
```bash
./run_functional_tests.sh
```

**Command (Run Single Test):**
You can run a specific test by name. The tool is flexible and accepts path-like strings (useful for tab completion).

```bash
# Run the '2player' test
./functional_test.py replay 2player

# Also works with paths (e.g. from tab completion)
./functional_test.py replay replay/2player
```

### Creating/Updating Functional Tests

**Record a New Test:**
1. Start recording mode:
   ```bash
   ./functional_test.py record my_new_test
   ```
2. Play the game.
3. Exit (ESC or close window).
4. Golden files will be saved to `goldens/my_new_test/`.

**Update Existing Test:**
If you made valid changes that affect the output (e.g., scoring logic change), update the goldens:
```bash
./functional_test.py rerecord 2player
```

## Troubleshooting

- **"No module named..."**: Ensure your `PYTHONPATH` is set correctly.
  ```bash
  export PYTHONPATH=$(pwd)/src:$(pwd)/../easing-functions:$(pwd)/../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH
  ```
- **Display Errors**: If running on a headless server, ensure you are not using `--visual`. The tests handle `SDL_VIDEODRIVER=dummy` automatically in default mode.
