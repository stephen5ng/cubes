# Major Refactoring Plan: BlockWords Cubes

## Executive Summary

This plan implements three high-impact architectural improvements to eliminate code duplication, improve testability, and reduce coupling:

1. **PlayerConfig Abstraction** - Eliminate scattered player-specific conditionals (7 patterns across 5 files)
2. **Input Management Extraction** - Extract input handling from pygamegameasync.py (~100 lines)
3. **MQTT Coordination Extraction** - Separate MQTT concerns from game loop (~50 lines)

**Total Impact**: Reduce pygamegameasync.py from 452 → ~250 lines, eliminate hardcoded player logic, improve testability.

---

## Implementation Phases

### Phase 1: PlayerConfig Abstraction (HIGHEST PRIORITY)

**Why First**: Most isolated change with highest maintainability impact. Eliminates scattered `if player == 0` conditionals.

#### 1.1 Create Core PlayerConfig System

**New file**: `src/config/player_config.py`

```python
@dataclass(frozen=True)
class PlayerConfig:
    """Configuration for a single player's display and behavior."""
    player_id: int
    shield_color: Color
    fader_color: Color
    rack_horizontal_offset: int  # Pixels from center
    tile_order_direction: int  # 1 for left-to-right, -1 for right-to-left
    selection_anchor: str  # "left" or "right"

    def get_letter_index(self, base_index: int, max_letters: int) -> int:
        """Transform letter index based on player-specific rules."""

    def get_selection_rect(self, select_count: int, letter_width: int,
                          max_letters: int, letter_height: int) -> pygame.Rect:
        """Calculate selection rectangle based on player configuration."""

class PlayerConfigManager:
    """Manages player configurations for all players."""

    def get_config(self, player_id: int) -> PlayerConfig:
        """Get configuration for a specific player."""

    def get_single_player_config(self) -> PlayerConfig:
        """Get configuration for single-player mode (centered display)."""
```

#### 1.2 Refactor Components to Use PlayerConfig

**File**: `src/rendering/rack_display.py`

Changes:
- Remove hardcoded arrays: `left_offset_by_player`, `rack_color_by_player`
- Add `player_config: PlayerConfig` to constructor
- Replace all player conditionals with `player_config` method calls
- Lines affected: 53-54 (arrays), 70 (color), 132-137 (letter flashing), 157-158 (positioning)

**File**: `src/rendering/metrics.py`

Changes:
- Update `get_select_rect(select_count, player_config)` signature
- Delegate to `player_config.get_selection_rect()`
- Lines affected: 60-68

**File**: `src/game/components.py`

Changes:
- Add `player_config: PlayerConfig` to Shield and Score constructors
- Replace `FADER_PLAYER_COLORS[self.player]` with `player_config.fader_color`
- Replace `PLAYER_COLORS[player]` with `player_config.shield_color`
- Lines affected: 99 (Shield color)

**File**: `src/ui/guess_display.py`

Changes:
- Add `player_config_manager: PlayerConfigManager` to constructor
- Remove hardcoded `PLAYER_COLORS` and `FADER_PLAYER_COLORS` arrays (lines 39-40)
- Get colors dynamically: `player_config_manager.get_config(player).shield_color`
- Lines affected: 39-40 (arrays), 151-152 (color usage)

**File**: `src/game/game_state.py`

Changes:
- Add `player_config_manager: PlayerConfigManager` to constructor
- Pass `player_config` to RackDisplay, Score, Shield when creating instances
- Inject config manager into PreviousGuessesDisplay

#### 1.3 Verification

```bash
# Unit tests for components
pytest tests/unit/test_score_display.py tests/unit/test_guess_display.py -v

# Integration tests for player-specific behavior
pytest tests/integration/test_multiplayer_gameplay.py -v
pytest tests/integration/test_previous_guesses_display.py -v

# All integration tests
pytest tests/integration/ -v
```

**Success Criteria**:
- [ ] All 33 integration tests pass
- [ ] All unit tests pass
- [ ] No hardcoded player conditionals in rendering code
- [ ] Single-player and two-player modes work identically

---

### Phase 2: Extract Input Management

**Why Second**: High value, reduces pygamegameasync.py significantly, minimal dependencies.

#### 2.1 Create Input Management Module

**New file**: `src/input/input_manager.py`

```python
class InputManager:
    """Centralizes all input event collection and distribution."""

    def __init__(self, replay_file: str = ""):
        self.replay_file = replay_file
        self.replayer = None  # GameReplayer instance if replay mode

    def get_pygame_events(self) -> list[dict]:
        """Collect pygame events (KEYDOWN, QUIT, JOYAXISMOTION, etc.)"""

    def get_mqtt_events(self, mqtt_queue: asyncio.Queue) -> list[dict]:
        """Drain MQTT queue into event list"""

    def get_replay_events(self) -> tuple[list[dict], list[dict], int]:
        """Get next replay frame (pygame_events, mqtt_events, timestamp_ms)"""

    def has_replay_events_remaining(self) -> bool:
        """Check if replay has more events"""
```

**New file**: `src/input/keyboard_handler.py`

```python
class KeyboardHandler:
    """Processes keyboard events with game state awareness."""

    def __init__(self, game: Game, input_controller: GameInputController):
        self.game = game
        self.input_controller = input_controller

    async def handle_event(self, key: str, keyboard_input: KeyboardInput, now_ms: int) -> None:
        """Process a single keyboard event"""
```

#### 2.2 Refactor pygamegameasync.py

**File**: `pygamegameasync.py`

Changes:
- Remove `_get_pygame_events()` → delegate to InputManager.get_pygame_events()
- Remove `_get_mqtt_events()` → delegate to InputManager.get_mqtt_events()
- Remove `_get_replay_events()` → delegate to InputManager.get_replay_events()
- Remove `handle_keyboard_event()` → delegate to KeyboardHandler.handle_event()
- Simplify `_handle_pygame_events()` to route to KeyboardHandler
- Add InputManager instance in `__init__()` or `setup_game()`

**Lines reduced**: ~450 → ~350 (removes ~100 lines)

#### 2.3 Verification

```bash
# Input and replay tests
pytest tests/integration/ -v -k "input or keyboard or replay"

# Full integration suite
pytest tests/integration/ -v
```

**Success Criteria**:
- [ ] All integration tests pass
- [ ] Replay functionality works identically
- [ ] Keyboard, gamepad, and cube inputs work
- [ ] Code reduction of ~100 lines achieved

---

### Phase 3: Extract MQTT Coordination

**Why Third**: Complements Phase 2, further simplifies game loop.

#### 3.1 Create MQTT Coordination Module

**New file**: `src/mqtt/mqtt_coordinator.py`

```python
class MQTTCoordinator:
    """Handles all MQTT message processing and routing."""

    def __init__(self, game: Game, app: App, publish_queue: asyncio.Queue):
        self.game = game
        self.app = app
        self.publish_queue = publish_queue

    async def handle_message(self, topic: str, payload: bytes | None, now_ms: int) -> None:
        """Route MQTT messages to appropriate handlers"""

    async def process_messages_task(self, mqtt_client, message_queue: asyncio.Queue) -> None:
        """Background task for MQTT message processing"""
```

#### 3.2 Refactor pygamegameasync.py

**File**: `pygamegameasync.py`

Changes:
- Remove `handle_mqtt_message()` → move to MQTTCoordinator.handle_message()
- Remove `_process_mqtt_messages()` → move to MQTTCoordinator.process_messages_task()
- Create MQTTCoordinator instance in `setup_game()`
- Update `run_single_frame()` to call coordinator.handle_message()

**Lines reduced**: ~350 → ~300 (removes ~50 lines)

#### 3.3 Verification

```bash
# MQTT-specific tests
pytest tests/integration/test_mqtt_protocol.py -v
pytest tests/integration/test_cube_state_sync.py -v

# Full integration suite
pytest tests/integration/ -v
```

**Success Criteria**:
- [ ] All MQTT integration tests pass
- [ ] cube/right/* messages processed correctly
- [ ] app/start and app/abort work
- [ ] Code reduction of ~50 lines achieved

---

### Phase 4: Extract Game Setup (OPTIONAL)

**Why Last**: Lower priority polish, completes pygamegameasync.py refactoring.

#### 4.1 Create Game Coordinator Module

**New file**: `src/game/game_coordinator.py`

```python
class GameCoordinator:
    """Manages game setup, initialization, and lifecycle."""

    async def setup_game(self, app: App, subscribe_client, publish_queue,
                        game_logger, output_logger, replay_file: str,
                        descent_mode: str, descent_duration_s: int,
                        record: bool, one_round: bool, min_win_score: int,
                        stars: bool) -> tuple[...]:
        """Setup all game components"""
```

#### 4.2 Refactor pygamegameasync.py

**File**: `pygamegameasync.py`

Changes:
- Move `setup_game()` logic to GameCoordinator
- Keep `run_single_frame()` and `main()` in pygamegameasync.py

**Lines reduced**: ~300 → ~200 (removes ~100 lines)

#### 4.3 Verification

```bash
pytest tests/integration/test_game_lifecycle.py -v
pytest tests/integration/test_auto_start.py -v
pytest tests/integration/ -v
```

**Success Criteria**:
- [ ] All lifecycle tests pass
- [ ] Game initialization works identically
- [ ] Final pygamegameasync.py size: ~200 lines (56% reduction from 452)

---

## Critical Files to Modify

### Phase 1 (PlayerConfig)
1. `src/config/player_config.py` - NEW (create PlayerConfig system)
2. `src/rendering/rack_display.py` - MODIFY (remove hardcoded arrays, use PlayerConfig)
3. `src/rendering/metrics.py` - MODIFY (update get_select_rect signature)
4. `src/game/components.py` - MODIFY (Shield, Score use PlayerConfig)
5. `src/ui/guess_display.py` - MODIFY (remove hardcoded color arrays)
6. `src/game/game_state.py` - MODIFY (inject PlayerConfigManager)
7. `tests/fixtures/game_factory.py` - MODIFY (inject PlayerConfigManager)

### Phase 2 (Input Management)
1. `src/input/input_manager.py` - NEW (create InputManager)
2. `src/input/keyboard_handler.py` - NEW (create KeyboardHandler)
3. `pygamegameasync.py` - MODIFY (extract input polling)

### Phase 3 (MQTT Coordination)
1. `src/mqtt/mqtt_coordinator.py` - NEW (create MQTTCoordinator)
2. `pygamegameasync.py` - MODIFY (extract MQTT handling)

### Phase 4 (Game Setup) - OPTIONAL
1. `src/game/game_coordinator.py` - NEW (create GameCoordinator)
2. `pygamegameasync.py` - MODIFY (extract setup logic)

---

## Test Strategy

### After Each Phase

```bash
# Run relevant unit tests
pytest tests/unit/ -v

# Run all integration tests (CRITICAL per CLAUDE.md)
pytest tests/integration/ -v

# Run functional tests if behavior changes
./run_functional_tests.sh
```

### Before Final Commit

Per CLAUDE.md requirements:

```bash
# CRITICAL: Run ALL integration tests before EVERY commit
pytest tests/integration/ -v

# Run unit tests
pytest tests/unit/ -v

# Run functional tests for feature changes
./run_functional_tests.sh
```

---

## Risk Mitigation

### High-Risk Areas

1. **PlayerConfig injection chain** - Must update all component constructors
   - Mitigation: Test each component separately with unit tests
   - Fallback: Keep PLAYER_COLORS/FADER_PLAYER_COLORS arrays in game_config.py

2. **Replay functionality** - Input refactoring could break replay
   - Mitigation: Test with existing replay files after Phase 2
   - Keep comprehensive replay tests

3. **MQTT message routing** - Critical for hardware integration
   - Mitigation: Comprehensive integration tests with mock MQTT
   - Test mqtt_protocol extensively

### Rollback Strategy

Each phase is independently reversible via git revert. Integration tests will catch regressions immediately.

---

## Success Metrics

### Code Quality
- [ ] pygamegameasync.py: 452 → ~250 lines (45% reduction after Phases 1-3)
- [ ] Zero hardcoded player conditionals in rendering code
- [ ] All modules have single, clear responsibility

### Test Coverage
- [ ] All 33 integration tests pass
- [ ] All unit tests pass
- [ ] Functional tests pass (per CLAUDE.md)

### Maintainability
- [ ] Adding a 3rd player requires only adding PlayerConfig entry
- [ ] New input devices can be added without modifying game loop
- [ ] MQTT handling is isolated and independently testable

---

## Future Benefits Enabled

This refactoring unlocks:
1. **3+ player support** - Just add PlayerConfig entries
2. **Theming system** - PlayerConfig per theme
3. **Better input device testing** - InputManager isolation
4. **Hardware-in-the-loop testing** - MQTTCoordinator mocking
5. **Easier visual customization** - All player-specific rendering in one place
