# Functional Test Migration Plan

**Goal**: Replace heavyweight replay-based functional tests with fast, MQTT-mocked integration tests similar to `test_shield_physics.py`

**Status**: Phase 5 Complete - Timed Mode Tests Migrated
**Created**: 2026-01-09
**Owner**: Team

---

## Executive Summary

Current functional tests replay entire game sessions through pygame, comparing output files against golden files. These tests are:
- **Slow**: Run through full pygame rendering pipeline (~2+ minutes total)
- **Heavy**: Require 14 replay directories with golden files (5937 lines of replays)
- **Brittle**: Break on timing changes, formatting differences, or benign output variations
- **Limited feedback**: Only verify output files match, not individual component behavior

**Proposed solution**: Replace with focused integration tests that:
- Mock at MQTT boundary (like `test_shield_physics.py`)
- Test specific game scenarios in isolation
- Run in <1 second each
- Provide clear assertions on game state
- Are easy to maintain and debug

---

## Current Functional Test Inventory

### Tests to Migrate (14 tests)

| Test Name | Lines | Category | What It Tests |
|-----------|-------|----------|---------------|
| `both_players_abc` | 8 | ABC Countdown | Both players press ABC simultaneously |
| `p1_only_abc` | 10 | ABC Countdown | Only Player 1 presses ABC |
| `p2_only_abc` | 8 | ABC Countdown | Only Player 2 presses ABC |
| `per_player_abc` | 13 | ABC Countdown | Per-player ABC tracking |
| `p1_starts_after_p0` | 17 | Sequential Start | P1 joins after P0 starts |
| `p2_starts_first` | 15 | Sequential Start | P2 starts before P0 |
| `sequential_start` | 12 | Sequential Start | Players start in sequence |
| `2player` | 57 | Multi-player | Two players competing |
| `single_player_p1_scoring` | 42 | Single Player | P1-only scoring |
| `yellow_line_pushback` | 11 | Timed Mode | Timed descent with yellow line |
| `gamepad` | 2008 | Input | Gamepad input handling (LARGE) |
| `sng` | 1865 | Stress Test | Complex game scenario (LARGE) |
| `stress_0.1` | 1871 | Stress Test | High-frequency input (LARGE) |
| **Total** | **5937** | | |

### Test Categories

1. **ABC Countdown (4 tests)**: Player start button sequences
2. **Sequential Start (3 tests)**: Multi-player join timing
3. **Multi-player (1 test)**: Two-player gameplay
4. **Single Player (1 test)**: Solo scoring validation
5. **Timed Mode (1 test)**: Time-based descent
6. **Input/Stress (3 tests)**: Input handling and stress

---

## Testing Philosophy: UI Behavior Coverage

### What These Tests Should Cover

These are **integration tests** that verify components work together to produce correct **observable behavior**. Unlike pure unit tests, they should validate UI-level changes and component interactions.

The tests have access to the full `Game` object with all components:
- `game.shields` - Shield state and positions
- `game.letter` - Letter position, velocity, state
- `game.scores` - Score displays and values
- `game.racks` - Rack tiles and highlights
- `game.guesses_manager` - Previous guesses display
- `game.running` - Game state
- `game.yellow_tracker` - Yellow line position (timed mode)

**Key Principle**: Test **observable outcomes** (positions, states, counts), not **rendering details** (pixels, fonts, exact timing).

### Test Boundaries

| Test Type | Validates | Example | Include? |
|-----------|-----------|---------|----------|
| **State** | Component properties change correctly | `shield.active == False` | ✅ YES |
| **Behavior** | Components interact properly | Letter bounces after collision | ✅ YES |
| **Position** | Elements move to correct locations | `letter.pos[1] < SHIELD_Y` | ✅ YES |
| **Visibility** | Elements show/hide appropriately | Shield disappears when inactive | ✅ YES |
| **Counts** | Correct number of UI elements | `len(game.shields) == 2` | ✅ YES |
| **Game State** | Scores, racks, guesses update | `score == 10` after "CATS" | ✅ YES |
| **Pixels** | Exact rendering output | Surface pixel colors | ❌ NO |
| **Timing** | Frame-perfect animations | Animation frame numbers | ❌ NO |
| **Styling** | Fonts, colors, sizes | Font size == 24 | ❌ NO |

### UI Behavior Examples to Test

#### ✅ Good: Observable Behavior

```python
async def test_shield_collision_deactivates_shield():
    """Shield becomes inactive after letter hits it."""
    game, mqtt, queue = await create_game()
    shield = Shield((100, 400), "SHIELD", 100, 0, 0)
    game.shields.append(shield)

    await run_until_collision(game)

    assert shield.active == False  # UI state changed
    assert shield.rect.y == 400    # Position unchanged

async def test_word_appears_in_previous_guesses():
    """Formed word appears in previous guesses display."""
    game, mqtt, queue = await create_game()
    await start_player(game, mqtt, player=0)

    await simulate_word_formation(game, "CATS", player=0)

    guesses = [g.word for g in game.guesses_manager.guesses]
    assert "CATS" in guesses  # UI element updated

async def test_rack_tiles_update_after_word():
    """Rack tiles replaced after word formation."""
    game, mqtt, queue = await create_game()
    await start_player(game, mqtt, player=0)

    tiles_before = game._app._player_racks[0].get_tiles().copy()
    await simulate_word_formation(game, "CAT", player=0)
    tiles_after = game._app._player_racks[0].get_tiles()

    assert tiles_before != tiles_after  # Rack refreshed
    assert len(tiles_after) == len(tiles_before)  # Same count

async def test_multiple_shields_independent():
    """Multiple shields operate independently."""
    game, mqtt, queue = await create_game()
    shield1 = Shield((100, 300), "FIRST", 100, 0, 0)
    shield2 = Shield((200, 400), "SECOND", 100, 0, 0)
    game.shields.extend([shield1, shield2])

    # Position letter to hit shield1
    game.letter.pos = [100, 290]
    await advance_frames(game, 5)

    assert shield1.active == False  # Hit shield deactivates
    assert shield2.active == True   # Other shield unaffected
```

#### ❌ Bad: Rendering Details

```python
# DON'T TEST: Pixel-level rendering
async def test_shield_renders_at_exact_pixel():
    surface = game.render_to_surface()
    pixel_color = surface.get_at((100, 400))
    assert pixel_color == (255, 0, 0)  # Too brittle!

# DON'T TEST: Animation frame timing
async def test_bounce_animation_frame_12():
    await advance_frames(game, 12)
    assert game.letter.animation_frame == 12  # Implementation detail

# DON'T TEST: Font rendering
async def test_shield_word_font_size():
    assert shield.font.size == 24  # Styling concern
```

### UI Behaviors by Category

#### Shield Mechanics
- Shield deactivation on collision
- Letter bounce physics after shield hit
- Multiple shields operate independently
- Shield word appears in previous guesses
- Shield blocks letter descent

#### Word Formation
- Tiles highlight during word formation
- Previous guesses list updates immediately
- Score display updates after word accepted
- Invalid word shows visual feedback (if applicable)
- Guess counter increments
- Word validation triggers correct state changes

#### Letter Descent & Position
- Letter column position tracks correctly
- Letter moves to correct Y position over time
- Yellow line descends slower than letter (timed mode)
- Letter pushed upward by yellow line
- Letter resets to top after word formation
- Letter stops at bottom of screen

#### Rack Management
- Tiles appear in correct rack positions
- Rack updates after word accepted
- Tiles removed/replaced correctly
- Multi-player racks remain independent
- Rack tiles match App rack state

#### Score Display
- Score increments by word length
- Bingo bonus adds correctly
- Per-player scores tracked independently
- Score display shows current value

---

## Migration Strategy

### Phase 0: Shield Mechanics Tests (Ongoing - expand `test_shield_physics.py`)

**Status**: ✅ Phase 0 Complete

`test_shield_physics.py` already demonstrates the MQTT-mocking pattern and validates UI behavior (shield deactivation, letter bounce). Expand it with additional shield scenarios:

#### Additional Tests Added:
- [x] `test_shield_deactivation_on_hit` - Shield.active becomes False
- [x] `test_multiple_shields_independent` - Multiple shields don't interfere
- [x] `test_shield_word_in_previous_guesses` - Shield word appears in UI
- [x] `test_shield_blocks_letter_descent` - Letter can't pass active shield

**Note**: `tests/integration/test_shield_lifecycle.py` was also added (16 tests), covering creation, sizing, animation, scoring, and cleanup.

**Example Addition** (from `test_shield_physics.py`):
```python
async def test_shield_deactivation_on_hit():
    """Verify shield active state deactivates on collision and moves off screen."""
    game, _mqtt, _queue = await create_test_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "TEST", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y)

    await run_until_condition(game, _queue, lambda fc, ms: not shield.active)

    assert not shield.active, "Shield should be deactivated after collision"
    assert shield.pos[1] >= game_config.SCREEN_HEIGHT, "Shield should move off screen"
```

**Effort**: 4 hours to add 5 additional test cases

---

### Phase 1: Test Infrastructure (Week 1)

**Goal**: Establish patterns and shared utilities
 
 **Status**: ✅ Complete

#### Tasks:
- [x] Create `FakeMqttClient` (✓ Done)
- [x] Refactor `test_shield_physics.py` as reference (✓ Done)
- [x] Create `tests/integration/` directory structure
- [x] Create `tests/fixtures/game_factory.py`:
  - Factory functions for common test setups
  - Mock MQTT + App + Game initialization
  - Scenario builders (single player, 2-player, etc.)
- [x] Create `tests/fixtures/mqtt_helpers.py`:
  - Helper to inject ABC button presses
  - Helper to inject neighbor reports
  - Helper to simulate cube guesses
  - Helper to verify MQTT publishes
- [x] Create `tests/assertions/game_assertions.py`:
  - Assert functions for game state
  - Assert functions for scoring
  - Assert functions for player state
- [x] Document test patterns in `docs/testing_patterns.md`

**Deliverables**:
```python
# Example fixture usage
from tests.fixtures.game_factory import create_game, simulate_abc_press

async def test_single_player_start():
    game, mqtt, queue = await create_game()
    await simulate_abc_press(mqtt, player=0, cube_set=0)
    # ... assertions
```

---

### Phase 1.5: Hardware Integration Tests (New)

**Goal**: Verify App-to-Hardware wiring and logic (regression prevention)

**Status**: ✅ Complete

#### Tests Created:
- `tests/integration/test_cube_app_interaction.py`:
  - `test_letter_lock_1_player_wiring`
  - `test_letter_lock_2_player_wiring`
  - `test_accept_new_letter_2_player_mapping`
  - `test_load_rack_skips_unstarted_players`
  - `test_guess_word_keyboard_player_mapping`

**Value**: Ensures core hardware interaction logic (position mapping, broadcasting) works correctly before layering complex gameplay tests. Prevents regressions like the "letter lock offset" bug.

---

### Phase 2: ABC Countdown Tests (Week 2)

**Goal**: Replace 4 ABC countdown tests
 
 **Status**: 🔄 In Progress (1/4 tests complete)

#### Tests to Create:
1. `tests/integration/test_abc_countdown.py`:
   - `test_both_players_abc_simultaneous` - Both press ABC together
   - `test_p0_only_abc` - Only P0 activates
   - `test_p1_only_abc` - Only P1 activates
   - `test_per_player_abc_tracking` - Per-player ABC state management

#### What to Test:

**Functional Behavior:**
- ABC sequence activation on button press
- Cube set IDs tracked correctly per player
- Countdown timers per player
- Game start triggers at countdown completion
- Non-participating players don't affect active players

**UI Behavior:**
- Game state transitions from not-running to running
- Racks populate with letters after game starts
- Both players' racks initialized independently
- Letter begins descent after game start
- Scores initialize to 0 for both players

#### Success Criteria:
- All 4 tests pass in <5s total
- Tests verify game state directly (not via output files)
- Clear failure messages showing what went wrong
- Tests run in headless mode

**Example Test Structure**:
```python
async def test_both_players_abc_simultaneous():
    """Test both players pressing ABC buttons simultaneously."""
    game, mqtt, queue = await create_game()

    # Simulate neighbor reports for both cube sets
    await inject_neighbor_topology(mqtt, player_0_cubes=[1,2,3], player_1_cubes=[11,12,13])

    # Both players press ABC at same time
    await simulate_abc_press(mqtt, player=0, cube_set=0, time_ms=1000)
    await simulate_abc_press(mqtt, player=1, cube_set=1, time_ms=1000)

    # Wait for countdown + game start
    await advance_time(game, countdown_duration_ms + 100)

    # Functional assertions
    assert_player_started(game, player=0)
    assert_player_started(game, player=1)
    assert_player_to_cube_set_mapping(game, {0: 0, 1: 1})
    assert game.running == True

    # UI behavior assertions
    assert len(game._app._player_racks[0].get_tiles()) > 0  # P0 rack populated
    assert len(game._app._player_racks[1].get_tiles()) > 0  # P1 rack populated
    assert game.scores[0].score == 0  # Score initialized
    assert game.scores[1].score == 0
    assert game.letter.letter is not None  # Letter active
```

---

### Phase 3: Sequential Start Tests (Week 3)

**Goal**: Replace 3 sequential start tests

**Status**: ✅ Complete

#### Tests Created:
2. `tests/integration/test_sequential_start.py`:
   - `test_p1_joins_after_p0_started` - P1 joins mid-game
   - `test_p1_starts_first` - P1 initiates, P0 joins later

#### What to Test:

**Functional Behavior:**
- Player can join after game starts
- Late joiner gets correct rack state
- Existing player unaffected by new joiner
- Player-to-cube-set mapping updates correctly
- ABC tracking clears for active players

**UI Behavior:**
- Late joiner's rack populates with correct tiles
- Existing player's rack unchanged by new joiner
- Late joiner's score initializes to 0
- Both players' UI elements visible and independent
- Letter position unaffected by new player joining

#### Key Differences from Phase 2:
- Game already running when second player joins
- Test rack synchronization for late joiners
- Verify existing gameplay continues uninterrupted

**Example**:
```python
async def test_p1_joins_after_p0_started():
    """Test P1 joining after P0 has already started playing."""
    game, mqtt, queue = await create_game()

    # P0 starts
    await start_player(game, mqtt, player=0, cube_set=0)
    assert game.running == True

    # P0 plays for a bit
    initial_score = game.scores[0].score
    await simulate_word_formation(game, mqtt, player=0, word="CAT")
    assert game.scores[0].score > initial_score

    # P1 joins mid-game
    await start_player(game, mqtt, player=1, cube_set=1, time_ms=5000)

    # Verify both active
    assert_player_started(game, player=0)
    assert_player_started(game, player=1)

    # Verify P1 has correct rack (UI behavior)
    p0_rack = game._app._player_racks[0].get_tiles()
    p1_rack = game._app._player_racks[1].get_tiles()
    assert len(p1_rack) > 0  # P1 rack populated
    assert p0_rack != p1_rack  # Independent racks

    # Verify P1 score initialized
    assert game.scores[1].score == 0

    # Verify P0 kept their score
    assert game.scores[0].score > initial_score
```

---

### Phase 4: Core Gameplay Tests (Week 4)

**Goal**: Replace 2 core gameplay tests (2player, single_player_p1)

#### Tests to Create:
3. `tests/integration/test_multiplayer_gameplay.py`:
   - `test_two_player_competitive` - Two players forming words
   - `test_two_player_scoring_independent` - Scores tracked separately
   - `test_two_player_rack_isolation` - Racks don't interfere

4. `tests/integration/test_single_player.py`:
   - `test_single_player_p0_scoring` - P0 solo gameplay
   - `test_single_player_p1_scoring` - P1 solo gameplay (coverage)

#### What to Test:

**Functional Behavior:**
- Word formation and scoring
- Independent rack management per player
- Letter descent and collision
- Previous guesses tracking
- Score accumulation

**UI Behavior:**
- Formed words appear in previous guesses display
- Score display updates immediately after word
- Rack tiles refresh after word formation
- Letter resets to top after word accepted
- Multi-player scores update independently
- Previous guesses color-coded by player (if applicable)

**Example**:
```python
async def test_two_player_competitive():
    """Test two players forming words simultaneously."""
    game, mqtt, queue = await create_game(player_count=2)
    await start_both_players(game, mqtt)

    # P0 forms "CAT" (score 3)
    p0_rack_before = game._app._player_racks[0].get_tiles().copy()
    await simulate_word_formation(game, mqtt, player=0, word="CAT", time_ms=1000)

    # Functional assertions
    assert game.scores[0].score == 3
    assert game.scores[1].score == 0

    # UI behavior assertions
    p0_rack_after = game._app._player_racks[0].get_tiles()
    assert p0_rack_before != p0_rack_after  # Rack refreshed
    assert "CAT" in [g.word for g in game.guesses_manager.guesses]  # Previous guesses updated

    # P1 forms "DOGS" (score 4)
    await simulate_word_formation(game, mqtt, player=1, word="DOGS", time_ms=2000)
    assert game.scores[0].score == 3
    assert game.scores[1].score == 4
    assert "DOGS" in [g.word for g in game.guesses_manager.guesses]

    # Verify independent racks (UI isolation)
    assert game._app._player_racks[0].get_tiles() != game._app._player_racks[1].get_tiles()

    # Verify both words in previous guesses
    all_guesses = [g.word for g in game.guesses_manager.guesses]
    assert "CAT" in all_guesses and "DOGS" in all_guesses
```

---

### Phase 5: Timed Mode Tests (Week 5)

**Goal**: Replace 1 timed mode test (yellow_line_pushback)

#### Tests to Create:
5. `tests/integration/test_timed_mode.py`:
   - `test_yellow_line_descent` - Yellow line falls slower
   - `test_letter_pushback_on_yellow_line` - Letters pushed by yellow line
   - `test_timed_game_duration` - Game ends at duration

#### What to Test:

**Functional Behavior:**
- Time-based descent strategy
- Yellow line speed (3x slower than letter)
- Letter pushback mechanics
- Game end trigger at duration
- Timed mode vs discrete mode differences

**UI Behavior:**
- Yellow line position descends at correct rate
- Letter position pushed upward when yellow line catches up
- Letter position advances smoothly (not discrete jumps)
- Yellow line visible throughout game
- Letter never descends below yellow line

**Example**:
```python
async def test_yellow_line_descent():
    """Test yellow line descends at correct rate (3x slower than letters)."""
    game, mqtt, queue = await create_game(descent_mode="timed", duration_s=120)
    await start_player(game, mqtt, player=0)

    # Track positions at intervals (UI behavior)
    letter_y_at_10s = await get_letter_y_at_time(game, 10000)
    yellow_y_at_10s = game.yellow_tracker.pos[1]

    # Yellow should be ~3x higher (slower descent)
    assert yellow_y_at_10s < letter_y_at_10s / 2, \
        f"Yellow line not slower: letter={letter_y_at_10s}, yellow={yellow_y_at_10s}"

    letter_y_at_30s = await get_letter_y_at_time(game, 30000)
    yellow_y_at_30s = game.yellow_tracker.pos[1]

    # Verify ratio maintained (functional)
    yellow_ratio = yellow_y_at_30s / letter_y_at_30s
    assert 0.3 < yellow_ratio < 0.4, f"Yellow ratio wrong: {yellow_ratio}"

    # Verify letter never goes below yellow (UI constraint)
    assert game.letter.pos[1] >= game.yellow_tracker.pos[1], \
        "Letter descended below yellow line"
```

---

### Phase 6: Input & Stress Tests (Week 6)

**Goal**: Decide fate of 3 large stress tests (gamepad, sng, stress_0.1)

#### Analysis:
These tests are **2000+ lines each** and test:
- Gamepad input mapping
- High-frequency input handling
- Complex game scenarios

#### Options:
1. **Convert to targeted tests**: Extract key scenarios, ignore replay fidelity
2. **Keep as E2E smoke tests**: Run occasionally, not in CI
3. **Delete**: If covered by other tests

#### Recommendation:
**Option 1 + Option 2 Hybrid**:
- Extract 3-5 key scenarios from each into focused tests
- Keep original replays as manual smoke tests (not automated)

#### Tests to Create:
6. `tests/integration/test_input_handling.py`:
   - `test_gamepad_axis_movement` - Joystick controls letter position
   - `test_gamepad_button_guess` - Button triggers guess
   - `test_keyboard_fallback` - Keyboard input works
   - `test_rapid_input_handling` - High-frequency inputs don't crash

7. `tests/integration/test_game_scenarios.py`:
   - `test_long_word_formation` - 7+ letter words
   - `test_rapid_guess_sequence` - Multiple guesses in quick succession
   - `test_rack_exhaustion` - Use all tiles in rack
   - `test_bingo_scoring` - 7-letter word bonus

#### What to Test:

**Functional Behavior:**
- Gamepad/keyboard input correctly triggers game actions
- High-frequency inputs don't cause crashes or race conditions
- Long words score correctly
- Bingo bonus awarded for 7-letter words
- Rack exhaustion handled gracefully

**UI Behavior:**
- Letter position responds to input (gamepad axis)
- Multiple rapid guesses all appear in previous guesses
- All guesses render correctly even under stress
- Score updates don't skip or duplicate
- UI remains responsive during rapid input
- Previous guesses display doesn't overflow or corrupt

**Example**:
```python
async def test_rapid_guess_sequence():
    """Test multiple guesses in rapid succession don't cause race conditions."""
    game, mqtt, queue = await create_game()
    await start_player(game, mqtt, player=0)

    # Rapid-fire 10 guesses
    words = ["CAT", "DOG", "HAT", "BAT", "RAT", "MAT", "SAT", "FAT", "PAT", "LAT"]
    for i, word in enumerate(words):
        await simulate_word_formation(game, mqtt, player=0, word=word, time_ms=i*100)

    # Functional assertions
    expected_score = sum(len(w) for w in words)
    assert game.scores[0].score == expected_score, \
        f"Score mismatch: expected {expected_score}, got {game.scores[0].score}"

    # Verify no crashes, state corruption
    assert game.running == True
    assert len(game._app._score_card.previous_guesses) == len(words)

    # UI behavior assertions
    displayed_guesses = [g.word for g in game.guesses_manager.guesses]
    assert len(displayed_guesses) == len(words), \
        "Not all guesses displayed in UI"
    for word in words:
        assert word in displayed_guesses, \
            f"Word '{word}' missing from previous guesses display"

    # Verify rack still valid after rapid operations
    rack = game._app._player_racks[0].get_tiles()
    assert len(rack) > 0, "Rack corrupted after rapid guesses"
    assert all(tile.letter for tile in rack), "Invalid tiles in rack"
```

---

## Migration Checklist

### Infrastructure
- [x] Create `tests/integration/` directory
- [x] Create `tests/fixtures/game_factory.py`
- [x] Create `tests/fixtures/mqtt_helpers.py`
- [x] Create `tests/assertions/game_assertions.py`
- [x] Document patterns in `docs/testing_patterns.md`

### Test Migration
- [x] Hardware Integration (Phase 1.5)
  - [x] `test_cube_app_interaction.py`
- [ ] Shield Mechanics (expand existing `test_shield_physics.py`)
  - [x] `test_shield_collision_bounces_letter` (exists)
  - [x] `test_shield_deactivation_on_hit`
  - [x] `test_multiple_shields_independent`
  - [x] `test_shield_word_in_previous_guesses`
  - [x] `test_shield_blocks_letter_descent`
- [ ] ABC Countdown (4 tests)
  - [x] `test_both_players_abc_simultaneous`
  - [x] `test_p0_only_abc`
  - [x] `test_p1_only_abc`
  - [x] `test_per_player_abc_tracking`
- [x] Sequential Start (2 tests)
  - [x] `test_p1_joins_after_p0_started`
  - [x] `test_p1_starts_first`
- [x] Core Gameplay (3 tests)
  - [x] `test_two_player_competitive`
  - [x] `test_single_player_p0_scoring`
  - [x] `test_single_player_p1_scoring`
- [x] Timed Mode (3 tests)
  - [x] `test_yellow_line_descent` (implemented as `test_yellow_descends_slower_than_red`)
  - [x] `test_letter_pushback_on_yellow_line` (implemented as `test_red_line_pushback_on_yellow_line`)
  - [x] `test_timed_game_duration` (implemented as `test_timed_game_ends_at_duration`)
- [x] Input Handling (4 tests)
  - [x] `test_gamepad_axis_movement`
  - [x] `test_gamepad_button_guess`
  - [x] `test_keyboard_fallback`
  - [x] `test_rapid_input_handling`
- [ ] Game Scenarios (4 tests)
  - [ ] `test_long_word_formation`
  - [ ] `test_rapid_guess_sequence`
  - [ ] `test_rack_exhaustion`
  - [ ] `test_bingo_scoring`

### CI Integration
- [ ] Add new tests to CI pipeline
- [ ] Run functional tests in CI (compare speed)
- [ ] Document speed improvements
- [ ] Update `run_functional_tests.sh` to run new tests
- [ ] Archive old replay tests (don't delete immediately)

---

## Success Metrics

### Speed
- **Current**: ~2+ minutes for all functional tests
- **Target**: <10 seconds for all new integration tests
- **Goal**: 12-20x speedup

### Maintainability
- **Current**: Update golden files on any change
- **Target**: Update assertions in code (no golden files)
- **Goal**: Self-documenting test assertions

### Coverage
- **Current**: End-to-end only (blackbox)
- **Target**: Component + integration (whitebox + graybox)
- **Goal**: Better error localization

### Developer Experience
- **Current**: Opaque failures, "update goldens" workflow
- **Target**: Clear assertion failures, fix in test code
- **Goal**: Faster debugging cycle

---

## Risk Mitigation

### Risk: Missing edge cases in conversion
**Mitigation**: Keep original functional tests until new tests proven stable (3+ months)

### Risk: MQTT mocking not realistic enough
**Mitigation**: Validate against real hardware periodically; add E2E tests for critical paths

### Risk: Tests too coupled to implementation
**Mitigation**: Focus on behavior/outcomes, not internal state; use helper functions

### Risk: Time investment vs value
**Mitigation**: Incremental migration; each phase delivers value; stop if not worth it

---

## Timeline

| Phase | Duration | Effort | Deliverable |
|-------|----------|--------|-------------|
| Phase 0: Shield Tests | Ongoing | 4 hrs | 5 additional shield tests |
| Phase 1: Infrastructure | 1 week | 16 hrs | Shared test utilities |
| Phase 1.5: Hardware Int. | 1 day | 8 hrs | 5 wiring tests |
| Phase 2: ABC Tests | 1 week | 12 hrs | 4 tests passing |
| Phase 3: Sequential Start | 1 week | 12 hrs | 2 tests passing |
| Phase 4: Core Gameplay | 1 week | 12 hrs | 2 tests passing |
| Phase 5: Timed Mode | 1 week | 8 hrs | 1 test passing |
| Phase 6: Input/Stress | 1 week | 16 hrs | 8 tests passing |
| **Total** | **6+ weeks** | **80 hrs** | **23 new tests** |

---

## Open Questions

1. **Should we delete replay tests immediately or keep as smoke tests?**
   - Recommendation: Archive for 3 months, then delete if new tests stable

2. **How to handle timing-sensitive tests (countdown delays)?**
   - Recommendation: Mock time like `test_integration.py` does

3. **Should input tests use real pygame events or mock input layer?**
   - Recommendation: Mock input layer (keyboard_input, gamepad_input)

4. **What to do with 2000+ line stress tests?**
   - Recommendation: Extract key scenarios, keep originals as manual tests

5. **How to validate MQTT message correctness?**
   - Recommendation: Add assertions on `fake_mqtt_client.published_messages`

---

## Next Steps

1. **Review this plan** with team
2. **Approve/modify** migration strategy
3. **Start Phase 1** infrastructure work
4. **Create tracking issue** for migration progress
5. **Set up weekly check-ins** to review progress

---

## Appendix: Test Pattern Examples

### Pattern 1: Basic Game Setup
```python
async def create_test_game(player_count=1, descent_mode="discrete"):
    """Factory for common test game setup."""
    dictionary = Dictionary(MIN_LETTERS, MAX_LETTERS)
    fake_mqtt = FakeMqttClient()
    publish_queue = asyncio.Queue()

    app = App(publish_queue, dictionary)
    await cubes_to_game.init(fake_mqtt)

    game = Game(
        the_app=app,
        letter_font=load_test_font(),
        game_logger=GameLogger(None),
        output_logger=OutputLogger(None),
        sound_manager=SoundManager(),
        rack_metrics=RackMetrics(),
        letter_beeps=[],
        descent_mode=descent_mode
    )

    return game, fake_mqtt, publish_queue
```

### Pattern 2: Simulating ABC Press
```python
async def simulate_abc_press(mqtt: FakeMqttClient, player: int, cube_set: int, time_ms: int = 0):
    """Simulate a player pressing ABC to start game."""
    topic = f"game/start_abc/{cube_set}"
    await mqtt.inject_message(topic, "start")
    # Process through cubes_to_game
    await process_mqtt_queue(mqtt, time_ms)
```

### Pattern 3: Assertions
```python
def assert_player_started(game: Game, player: int):
    """Assert a player has started their game."""
    assert cubes_to_game.has_player_started_game(player), \
        f"Player {player} should have started but didn't"

def assert_score(game: Game, player: int, expected: int):
    """Assert player score matches expected."""
    actual = game.scores[player].score
    assert actual == expected, \
        f"Player {player} score: expected {expected}, got {actual}"
```

### Pattern 4: UI Behavior Assertions
```python
def assert_shield_deactivated(shield: Shield):
    """Assert shield has been deactivated after collision."""
    assert shield.active == False, "Shield should be deactivated after hit"
    assert shield.health <= 0, f"Shield health should be 0 or less, got {shield.health}"

def assert_word_in_previous_guesses(game: Game, word: str):
    """Assert word appears in previous guesses display."""
    guesses = [g.word for g in game.guesses_manager.guesses]
    assert word in guesses, \
        f"Word '{word}' not found in previous guesses: {guesses}"

def assert_rack_populated(game: Game, player: int):
    """Assert player's rack has valid tiles."""
    rack = game._app._player_racks[player].get_tiles()
    assert len(rack) > 0, f"Player {player} rack is empty"
    assert all(tile.letter for tile in rack), \
        f"Player {player} rack has invalid tiles"

def assert_letter_position_in_range(game: Game, min_y: float, max_y: float):
    """Assert letter is within expected Y position range."""
    letter_y = game.letter.pos[1]
    assert min_y <= letter_y <= max_y, \
        f"Letter Y position {letter_y} not in range [{min_y}, {max_y}]"

def assert_independent_racks(game: Game, player0: int, player1: int):
    """Assert two players have independent racks."""
    rack0 = game._app._player_racks[player0].get_tiles()
    rack1 = game._app._player_racks[player1].get_tiles()
    assert rack0 != rack1, \
        f"Players {player0} and {player1} have identical racks (should be independent)"
```

---

**Document Version**: 1.2
**Last Updated**: 2026-01-09
**Status**: Phase 1 Infrastructure Complete
