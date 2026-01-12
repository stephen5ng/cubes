# Unified Descent System Migration - First Attempt

## Goal
Remove the discrete/timed mode distinction and replace it with a unified time-based system where infinite duration (None) enables event-based descent only.

## Design Decisions Made

### 1. Parameters
**Old System:**
- `descent_mode: str = "discrete"` - Either "discrete" or "timed"
- `timed_duration_s: int = game_config.TIMED_DURATION_S` - Duration in seconds

**New System:**
- `game_duration_s: Optional[int] = None` - Game duration in seconds (None = infinite/event-based only)
- `event_descent_amount: int = 0` - Pixels to descend per event trigger

### 2. Mode Mapping
- **Old "discrete" mode** → `game_duration_s=None, event_descent_amount=Letter.Y_INCREMENT`
- **Old "timed" mode** → `game_duration_s=10, event_descent_amount=0`
- **New hybrid mode** → `game_duration_s=10, event_descent_amount=5` (both time and events)

### 3. Yellow Line Behavior
- **Timed mode (game_duration_s > 0):** Yellow line exists, descends 3x slower than red line
- **Infinite mode (game_duration_s = None):** Yellow line does not exist (yellow_tracker/yellow_source = None)

## Implementation

### Created: UnifiedDescentStrategy
```python
class UnifiedDescentStrategy(DescentStrategy):
    """Unified descent strategy combining time-based and event-based descent."""

    def __init__(self, game_duration_s: Optional[int], total_height: int, event_descent_amount: int = 0):
        # Calculate time-based descent rate
        if game_duration_s is None or game_duration_s <= 0:
            self.descent_rate = 0.0  # Infinite - no time-based descent
            self.game_duration_ms = 0
        else:
            self.game_duration_ms = game_duration_s * 1000
            self.descent_rate = total_height / self.game_duration_ms

        self.event_descent_amount = event_descent_amount
        self.pending_event_descent = 0
        self.total_height = total_height
        self.start_time_ms = 0
        self.last_y = 0

    def trigger_descent(self):
        """Trigger event-based descent (e.g., letter hits rack)."""
        self.pending_event_descent += self.event_descent_amount

    def update(self, current_y: int, now_ms: int, height: int) -> Tuple[int, bool]:
        """Calculate position from time-based + event-based descent."""
        # Time-based component
        elapsed_ms = now_ms - self.start_time_ms
        time_based_y = min(self.total_height, int(elapsed_ms * self.descent_rate))

        # Event-based component (clamped to not exceed total height)
        event_based_y = min(self.pending_event_descent, self.total_height - time_based_y)

        # Combined position
        target_y = min(time_based_y + event_based_y, self.total_height)

        # Consume applied event descent
        if event_based_y > 0:
            self.pending_event_descent -= event_based_y

        # Check if we moved
        moved = target_y > self.last_y
        self.last_y = target_y

        return (target_y, moved)

    def reset(self, now_ms: int):
        """Reset strategy state for new game."""
        self.start_time_ms = now_ms
        self.last_y = 0
        self.pending_event_descent = 0
```

### Modified Files

#### 1. `src/game/descent_strategy.py`
- Added `UnifiedDescentStrategy` class (lines 102-200)
- Kept `DiscreteDescentStrategy` and `TimeBasedDescentStrategy` for backwards compatibility

#### 2. `src/game/game_state.py`
**Changes to `Game.__init__`:**
```python
# OLD:
def __init__(self, ..., descent_mode: str = "discrete", timed_duration_s: int = game_config.TIMED_DURATION_S)

# NEW:
def __init__(self, ..., game_duration_s: Optional[int] = game_config.TIMED_DURATION_S, event_descent_amount: int = 0)
```

**Red line strategy creation (lines 57-62):**
```python
descent_strategy = UnifiedDescentStrategy(
    game_duration_s=game_duration_s,
    total_height=game_height,
    event_descent_amount=event_descent_amount
)
```

**Yellow line creation (lines 74-92):**
```python
if game_duration_s is not None and game_duration_s > 0:
    yellow_duration_s = game_duration_s * 3
    yellow_strategy = UnifiedDescentStrategy(
        game_duration_s=yellow_duration_s,
        total_height=game_height,
        event_descent_amount=0  # Yellow doesn't respond to events
    )
    self.yellow_tracker = PositionTracker(yellow_strategy)
    self.yellow_source = LetterSource(...)
else:
    # Infinite mode - no yellow line
    self.yellow_tracker = None
    self.yellow_source = None
```

**Changes to `accept_letter()` (line 194):**
```python
async def accept_letter(self, now_ms: int) -> None:
    """Accept the falling letter into the rack and trigger red line descent."""
    self.letter.descent_strategy.trigger_descent()  # NEW: Trigger event-based descent
    await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index(), now_ms)
    # ...
```

**Changes to `start()` (lines 169-170):**
```python
if self.yellow_tracker is not None:  # NEW: Check for None
    self.yellow_tracker.reset(now_ms)
```

**Changes to `update()` (lines 248-282):**
- Added null checks for `yellow_tracker` and `yellow_source`
- Updated shield collision to check if yellow_tracker exists before pushing red to yellow

#### 3. `src/game/letter.py`
**Added to `start()` method (line 74):**
```python
def start(self, now_ms: int) -> None:
    # ... existing initialization ...
    self.descent_strategy.reset(now_ms)  # NEW: Reset strategy on start
```

#### 4. `src/rendering/animations.py`
**Removed `descent_mode` parameter from `LetterSource.__init__` (line 62):**
```python
# OLD:
def __init__(self, letter, x: int, width: int, initial_y: int, descent_mode: str, color: pygame.Color = None)

# NEW:
def __init__(self, letter, x: int, width: int, initial_y: int, color: pygame.Color = None)
```

#### 5. `tests/fixtures/game_factory.py`
**Updated `create_test_game()` signature (line 97):**
```python
# OLD:
async def create_test_game(descent_mode: str = "discrete", visual: Optional[bool] = None,
                           player_count: int = 1, timed_duration_s: int = game_config.TIMED_DURATION_S)

# NEW:
async def create_test_game(game_duration_s: Optional[int] = None, event_descent_amount: int = None,
                           visual: Optional[bool] = None, player_count: int = 1)
```

**Added default parameter logic (lines 134-137):**
```python
# Default to infinite mode with event-based descent (old "discrete" mode behavior)
if event_descent_amount is None:
    from game.letter import Letter
    event_descent_amount = Letter.Y_INCREMENT if game_duration_s is None else 0
```

**Updated `create_game_with_started_players()` similarly**

#### 6. All Integration Test Files
Updated all test files to use new parameters:

**Pattern for infinite/event-based mode (old "discrete"):**
```python
# OLD:
game, mqtt, queue = await create_test_game(descent_mode="discrete")

# NEW:
game, mqtt, queue = await create_test_game(game_duration_s=None, event_descent_amount=Letter.Y_INCREMENT)
```

**Pattern for timed mode:**
```python
# OLD:
game, mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=10)

# NEW:
game, mqtt, queue = await create_test_game(game_duration_s=10)
```

**Files modified:**
- `tests/integration/test_abc_countdown.py` - Added Letter import, updated 4 tests
- `tests/integration/test_cube_app_interaction.py` - Added Letter import, updated 5 tests
- `tests/integration/test_game_modes.py` - Complete rewrite of 4 tests for new system
- `tests/integration/test_letter_descent.py` - Updated 6 test calls
- `tests/integration/test_rack_synchronization.py` - Added Letter import, updated 1 test
- `tests/integration/test_sequential_start.py` - Added Letter import, updated 2 tests
- `tests/integration/test_timed_mode.py` - Updated 3 tests

## Test Results

### Final Status: **101 passing, 4 failing** (96% pass rate)

### Passing Test Categories (101 tests)
✅ ABC countdown (4/4)
✅ Cube/app interaction (5/5)
✅ Cube state sync (3/3)
✅ Game lifecycle (5/5)
✅ Game modes (4/4) - **Completely rewritten for new system**
✅ Game scenarios (4/4)
✅ Input handling (4/4)
✅ Letter descent (5/8) - **3 failing**
✅ MQTT protocol (3/3)
✅ Multiplayer gameplay (3/3)
✅ Player mapping (5/5)
✅ Previous guesses display (5/5)
✅ Rack fair play (7/7)
✅ Rack synchronization (3/3)
✅ Scoring rules (6/6)
✅ Sequential start (2/2)
✅ Shield lifecycle (17/17)
✅ Shield physics (5/5)
✅ Single player (2/2)
✅ Timed mode (2/3) - **1 failing**
✅ Word validation (6/6)

### Failing Tests (4)

All failures show red line at **182/221 pixels (82%)** when expecting **221/221 pixels (100%)** after game duration.

#### 1. `test_letter_descent.py::test_letters_fall_at_constant_speed`
```python
game, mqtt, queue = await create_test_game(game_duration_s=1)
game.letter.start(0)
await advance_seconds(game, queue, 0.5)  # ✅ Passes: ~50% descent
await advance_seconds(game, queue, 0.55) # ❌ Fails: 82% descent (expected 100%)
```
**Error:** `AssertionError: Expected ~100% drop, got 0.82`

#### 2. `test_letter_descent.py::test_letter_collision_with_rack_bottom`
```python
game, mqtt, queue = await create_test_game(game_duration_s=2)
# Letter should hit rack bottom and get accepted
```
**Error:** `AssertionError: Expected X, got ?` (letter not accepted, becomes "!")

#### 3. `test_letter_descent.py::test_letter_position_resets_after_word_accepted`
```python
game, mqtt, queue = await create_test_game(game_duration_s=2)
# Letter should reset to top after acceptance
```
**Error:** `AssertionError: Letter should reset to top area, got 155` (stuck mid-screen)

#### 4. `test_timed_mode.py::test_timed_game_ends_at_duration`
```python
game, mqtt, queue = await create_test_game(game_duration_s=30)
await advance_seconds(game, queue, 25)  # ✅ Passes: still running
await advance_seconds(game, queue, 10)  # ❌ Fails: game still running (should have ended)
```
**Error:** `AssertionError: Game should have ended after duration expired`

## Analysis of Failures

### Common Pattern
All failures involve timed mode showing **82% descent** instead of **100%** after the full game duration.

**Math check:**
- Expected: 221 pixels / 1000ms = 0.221 pixels/ms
- Actual: 182 pixels / 1000ms = 0.182 pixels/ms
- Ratio: 182/221 = 0.823 = **82.3%**

### Possible Causes

1. **Frame timing issue:** Tests use 16ms frames (60 FPS). After 1000ms, we've actually only advanced `1000/16 = 62.5` frames, which is `62 * 16 = 992ms`. This gives us `992/1000 = 99.2%` which doesn't match.

2. **Height calculation mismatch:** The `game_height` passed to strategy might differ from `letter.height`:
   ```python
   # In Game.__init__:
   game_height = game_config.SCREEN_HEIGHT - (self.rack_metrics.letter_height + letter_y)

   # In Letter.__init__:
   self.height = SCREEN_HEIGHT - (rack_metrics.letter_height + initial_y)
   ```
   These should be identical, but worth verifying.

3. **Strategy start time issue:** If `strategy.reset()` is called at a different time than `game.start()`, the elapsed time calculation would be off.

4. **Update order issue:** The strategy might not be getting updated on the final frame, or there's an off-by-one error in the frame loop.

5. **Integer truncation:** The `int(elapsed_ms * self.descent_rate)` might be losing precision that accumulates to 18% error.

### Why 82% Specifically?
The consistency of 82% across all failures suggests a systematic error, not a random timing issue. Possibilities:
- A constant offset (e.g., 1000ms - 180ms = 820ms)
- A multiplier error (e.g., using seconds instead of milliseconds somewhere)
- Missing the last 10-12 frames of descent

## What Worked Well

1. **Strategy pattern design** - UnifiedDescentStrategy cleanly combines both modes
2. **Yellow line conditional creation** - Properly handles None case
3. **Event-based triggering** - `trigger_descent()` mechanism works correctly
4. **Test migration** - 101/105 tests pass with straightforward parameter updates
5. **Backwards compatibility** - Old strategies still exist for reference

## What Needs Investigation

1. **82% descent calculation** - Root cause of the 18% shortfall
2. **Frame timing** - How `advance_seconds()` interacts with strategy updates
3. **Letter ending behavior** - Why letter becomes "!" instead of being accepted
4. **Game end detection** - Why game doesn't end when red line reaches bottom

## Recommendations for Next Attempt

### Option 1: Incremental Migration
1. Start by adding UnifiedDescentStrategy alongside existing strategies
2. Add a single test that creates both old and new strategies and verifies identical behavior
3. Debug the 82% issue before touching any existing code
4. Only after perfect parity, begin migrating tests one file at a time

### Option 2: Debug Current Implementation
1. Add extensive logging to UnifiedDescentStrategy.update()
2. Create a minimal test that shows the descent calculation step-by-step
3. Compare frame-by-frame with old TimeBasedDescentStrategy
4. Fix the calculation issue
5. Verify all 105 tests pass

### Option 3: Check Old Implementation First
1. Revert all changes
2. Add tests that verify old TimeBasedDescentStrategy hits 100% after duration
3. If old implementation also shows 82%, the tests might be wrong
4. If old implementation hits 100%, compare implementations line-by-line

## Files Changed (Summary)

### Source Code (5 files)
- `src/game/descent_strategy.py` - Added UnifiedDescentStrategy
- `src/game/game_state.py` - Updated __init__, accept_letter, start, update
- `src/game/letter.py` - Added strategy.reset() to start()
- `src/rendering/animations.py` - Removed descent_mode parameter

### Test Infrastructure (1 file)
- `tests/fixtures/game_factory.py` - Updated create_test_game signature and logic

### Integration Tests (8 files)
- `tests/integration/test_abc_countdown.py`
- `tests/integration/test_cube_app_interaction.py`
- `tests/integration/test_game_modes.py`
- `tests/integration/test_letter_descent.py`
- `tests/integration/test_rack_synchronization.py`
- `tests/integration/test_sequential_start.py`
- `tests/integration/test_timed_mode.py`
- *(test_player_mapping.py had no descent_mode usage)*

### New Documentation (1 file)
- `docs/unified_descent_migration_attempt.md` - This document

## Next Steps

**Before proceeding, decide:**
1. Should we debug the current 82% issue or revert and start fresh?
2. Should we verify the old TimeBasedDescentStrategy actually achieves 100% descent?
3. Should we add unit tests for UnifiedDescentStrategy before integration testing?

**If debugging current implementation:**
- Add print statements to track descent calculation frame-by-frame
- Compare old vs new strategy side-by-side in same test
- Check if test framework's time mocking is correct

**If reverting and starting fresh:**
- Create unit tests showing UnifiedDescentStrategy perfectly mimics old behavior
- Migrate one component at a time (strategy → Game → Letter → tests)
- Keep old code working until new code passes all tests
