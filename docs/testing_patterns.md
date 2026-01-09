# Integration Testing Patterns

This document describes how to use the new integration testing infrastructure for the BlockWords game.

## Overview

The integration test framework is designed to run quickly, mock at the MQTT boundary, and verify game logic and UI state without full hardware or heavy functional test overhead.

### Key Components

1.  **Fixtures (`tests/fixtures/`)**:
    *   `game_factory.py`: Provides `create_test_game` to set up a mock environment and `run_until_condition` for simulation.
    *   `mqtt_helpers.py`: Helpers to inject MQTT messages (button presses, physical cube moves).
2.  **Assertions (`tests/assertions/`)**:
    *   `game_assertions.py`: Domain-specific assertions like `assert_player_started`.
3.  **Entry Point**: `tests/conftest.py` handles path setup and headless mode.

## Running Tests

### Run All Integration Tests
```bash
python3 -m pytest tests/integration/
```

### Run a Specific Test File
```bash
python3 -m pytest tests/integration/test_shield_physics.py
```

### Useful Options
- `--visual`: Run tests with a visible window (disables dummy SDL driver).
- `-s`: Show stdout/debug prints.
- `-v`: Verbose output.
- `--tb=short`: Concise traceback on failure.

## Visual Mode

By default, integration tests run in **headless mode** using the Pygame `dummy` video driver. This is faster and suitable for CI.

To watch the game state and animations:
```bash
python3 -m pytest tests/integration/test_shield_physics.py --visual
```

## Writing a New Test

Use the `@async_test` decorator and `create_test_game` factory.

```python
from tests.fixtures.game_factory import create_test_game, run_until_condition, async_test
from tests.fixtures.mqtt_helpers import inject_neighbor_report, process_mqtt_queue

@async_test
async def test_my_feature():
    # 1. Setup
    game, mqtt, queue = await create_test_game()
    
    # 2. Inject Hardware Events
    await inject_neighbor_report(mqtt, 'cube1', 'cube2')
    await process_mqtt_queue(game, queue, mqtt, 0)
    
    # 3. Simulate and Assert
    # Run until a condition is met
    found = await run_until_condition(game, queue, lambda: game.running)
    assert found
```

## Simulation Time

The framework uses a virtual clock. `run_until_condition` updates the game state in discrete steps (default 16ms per frame). `pygame.time.get_ticks()` is automatically patched to stay in sync with the simulation.
