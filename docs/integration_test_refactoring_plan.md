# Integration Test Refactoring Plan

## Overview
This plan addresses code quality, testability, and maintainability issues identified in the integration test suite. The work is organized into 4 phases to minimize risk and maintain test coverage throughout the refactoring.

**Estimated Total Effort:** 3-4 weeks
**Risk Level:** Medium (touching test infrastructure affects all tests)

---

## Phase 1: Foundation - Test Infrastructure & Shared Utilities
**Duration:** 4-5 days
**Goal:** Consolidate duplicated code and create reusable test infrastructure

### Task 1.1: Consolidate Helper Functions
**Files to modify:**
- `tests/fixtures/game_factory.py`
- `tests/fixtures/test_helpers.py` (NEW)
- `tests/integration/test_word_validation.py`
- `tests/integration/test_scoring_rules.py`
- `tests/integration/test_mqtt_protocol.py`
- `tests/integration/test_cube_state_sync.py`

**Implementation Steps:**

1. Create `tests/fixtures/test_helpers.py`:
```python
"""Shared test helper functions used across integration tests."""
import asyncio
from typing import Optional
from core.dictionary import Dictionary
from core.app import App

def update_app_dictionary(app: App, new_dictionary: Dictionary) -> None:
    """Update dictionary references across all App components.

    Args:
        app: Application instance
        new_dictionary: Dictionary instance to use

    Note:
        Updates App, ScoreCard, and RackManager dictionary references
        to ensure consistency across components.
    """
    app._dictionary = new_dictionary
    app._score_card.dictionary = new_dictionary
    app.rack_manager.dictionary = new_dictionary


async def drain_mqtt_queue(mqtt, queue) -> None:
    """Process all pending MQTT messages from queue to client.

    Args:
        mqtt: FakeMqttClient instance
        queue: asyncio.Queue containing pending MQTT messages

    Note:
        Drains queue and publishes all messages to the fake client.
        Useful for ensuring all async MQTT operations complete before assertions.
    """
    while not queue.empty():
        item = queue.get_nowait()
        if isinstance(item, tuple):
            topic, payload, retain, *_ = item
            await mqtt.publish(topic, payload, retain)
        else:
            await mqtt.publish(item.topic, item.payload)
```

2. Update imports in all test files:
```python
# OLD (in test_word_validation.py, test_scoring_rules.py, etc.)
def update_app_dictionary(app, new_dictionary):
    app._dictionary = new_dictionary
    app._score_card.dictionary = new_dictionary
    app.rack_manager.dictionary = new_dictionary

# NEW
from tests.fixtures.test_helpers import update_app_dictionary
```

3. Remove duplicate definitions (6 files contain `drain_queue` variants)

**Acceptance Criteria:**
- [x] All duplicate helper functions removed from individual test files
- [x] New `test_helpers.py` module created with consolidated helpers
- [x] All tests pass with updated imports
- [x] Run `pytest tests/integration/ -v` - all green

**Files Changed:** ~10 files
**Lines Removed:** ~100 lines
**Lines Added:** ~40 lines

---

### Task 1.2: Create IntegrationTestContext Builder
**Files to create:**
- `tests/fixtures/test_context.py` (NEW)

**Implementation Steps:**

1. Create test context builder:
```python
"""Test context builders for integration tests."""
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from game.game_state import Game
from testing.fake_mqtt_client import FakeMqttClient
from tests.fixtures.test_helpers import drain_mqtt_queue


@dataclass
class GuessResult:
    """Result of a guess operation in tests."""
    shield_created: bool
    score_change: int
    border_color: Optional[str]
    flash_sent: bool


class IntegrationTestContext:
    """High-level test context for integration tests.

    Encapsulates common setup, assertion, and interaction patterns
    to reduce boilerplate and improve test readability.

    Example:
        ctx = await IntegrationTestContext.create(players=[0])
        result = await ctx.make_guess(["0", "1"], player=0)
        ctx.assert_border_color("0x07E0")  # green
        ctx.assert_flash_sent(cube_id=1)
    """

    def __init__(self, game: Game, mqtt: FakeMqttClient, queue: asyncio.Queue):
        self.game = game
        self.mqtt = mqtt
        self.queue = queue
        self._initial_scores: Dict[int, int] = {}

    @classmethod
    async def create(cls, players: List[int] = [0], **game_kwargs):
        """Create a new test context with game initialized.

        Args:
            players: List of player IDs to initialize
            **game_kwargs: Additional arguments for create_game_with_started_players

        Returns:
            IntegrationTestContext instance ready for testing
        """
        from tests.fixtures.game_factory import create_game_with_started_players
        game, mqtt, queue = await create_game_with_started_players(
            players=players,
            **game_kwargs
        )
        ctx = cls(game, mqtt, queue)
        ctx._capture_initial_state()
        return ctx

    def _capture_initial_state(self):
        """Capture initial state for comparison."""
        for i in range(len(self.game.scores)):
            self._initial_scores[i] = self.game.scores[i].score

    async def make_guess(
        self,
        tile_ids: List[str],
        player: int = 0,
        now_ms: int = 1000
    ) -> GuessResult:
        """Make a guess and return structured result.

        Args:
            tile_ids: List of tile IDs forming the guess
            player: Player making the guess
            now_ms: Timestamp for the guess

        Returns:
            GuessResult with outcome details
        """
        initial_shield_count = len(self.game.shields)
        initial_score = self.game.scores[player].score

        self.mqtt.clear_published()

        await self.game._app.guess_tiles(
            tile_ids,
            move_tiles=False,
            player=player,
            now_ms=now_ms
        )
        await asyncio.sleep(0)
        await drain_mqtt_queue(self.mqtt, self.queue)

        shield_created = len(self.game.shields) > initial_shield_count
        score_change = self.game.scores[player].score - initial_score

        # Get border color
        from hardware.cubes_to_game import state
        cube_set = self.game._app._player_to_cube_set.get(player, 0)
        border_color = state.cube_set_managers[cube_set].border_color

        # Check for flash
        flash_messages = [m for m in self.mqtt.published_messages if "flash" in m[0]]
        flash_sent = len(flash_messages) > 0

        return GuessResult(
            shield_created=shield_created,
            score_change=score_change,
            border_color=border_color,
            flash_sent=flash_sent
        )

    def assert_score(self, player: int, expected: int, msg: str = ""):
        """Assert player score matches expected value."""
        actual = self.game.scores[player].score
        assert actual == expected, (
            f"{msg}\nPlayer {player} score mismatch: "
            f"expected {expected}, got {actual}"
        )

    def assert_score_change(self, player: int, expected_delta: int):
        """Assert player score changed by expected amount."""
        initial = self._initial_scores[player]
        actual = self.game.scores[player].score
        actual_delta = actual - initial
        assert actual_delta == expected_delta, (
            f"Score change mismatch for player {player}: "
            f"expected +{expected_delta}, got +{actual_delta} "
            f"(initial={initial}, current={actual})"
        )

    def assert_border_color(self, expected_color: str, cube_set: int = 0):
        """Assert cube set has expected border color."""
        from hardware.cubes_to_game import state
        actual = state.cube_set_managers[cube_set].border_color
        assert actual == expected_color, (
            f"Border color mismatch: expected {expected_color}, got {actual}"
        )

    def assert_flash_sent(self, cube_id: Optional[int] = None):
        """Assert flash message was sent to specified cube (or any cube)."""
        flash_msgs = [m for m in self.mqtt.published_messages if "flash" in m[0]]

        if cube_id is not None:
            cube_flashes = [m for m in flash_msgs if f"cube/{cube_id}/flash" in m[0]]
            assert len(cube_flashes) > 0, (
                f"No flash message sent to cube {cube_id}. "
                f"Flash messages: {[m[0] for m in flash_msgs]}"
            )
        else:
            assert len(flash_msgs) > 0, "No flash messages sent to any cube"

    def assert_shield_created(self, expected_word: str):
        """Assert a shield was created with expected word."""
        shields_with_word = [s for s in self.game.shields if s.letters == expected_word]
        assert len(shields_with_word) > 0, (
            f"No shield created with word '{expected_word}'. "
            f"Shields: {[s.letters for s in self.game.shields]}"
        )
```

2. Create example refactored test:
```python
# BEFORE (test_mqtt_protocol.py:91-120)
@async_test
async def test_good_guess_feedback():
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app

    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])
    await drain_queue()
    mqtt.clear_published()

    tiles_in_guess = ["0", "1"]
    await app.hardware.good_guess(queue, tiles_in_guess, 0, 0, 1000)
    await asyncio.sleep(0.1)
    await drain_queue()

    c1_flash = mqtt.get_published("cube/1/flash")
    assert len(c1_flash) > 0

    from hardware.cubes_to_game import state
    manager = state.cube_set_managers[0]
    assert manager.border_color == "0x07E0"

# AFTER
@async_test
async def test_good_guess_feedback():
    """Verify good guess triggers green border and flash."""
    ctx = await IntegrationTestContext.create(players=[0])

    result = await ctx.make_guess(["0", "1"], player=0)

    ctx.assert_border_color("0x07E0")  # Green
    ctx.assert_flash_sent(cube_id=1)
    assert result.flash_sent
```

**Acceptance Criteria:**
- [ ] `IntegrationTestContext` class created with core methods
- [ ] At least 3 tests refactored to use new context (as proof of concept)
- [ ] Refactored tests are shorter and more readable
- [ ] All tests pass

**Files Changed:** 4-5 files
**Lines Removed:** ~60 lines
**Lines Added:** ~200 lines (but net reduction in test code)

---

### Task 1.3: Improve Dictionary Test Data Management
**Files to modify:**
- `core/dictionary.py`
- `tests/fixtures/dictionary_helpers.py` (NEW)
- All tests using temp dictionary files (~6 files)

**Implementation Steps:**

1. Add factory method to `Dictionary`:
```python
# In core/dictionary.py

class Dictionary:
    # ... existing code ...

    @classmethod
    def from_words(
        cls,
        words: List[str],
        bingos: Optional[List[str]] = None,
        min_letters: int = 3,
        max_letters: int = 6
    ) -> 'Dictionary':
        """Create a dictionary from word lists without file I/O.

        Primarily for testing - allows in-memory dictionary creation.

        Args:
            words: List of valid words
            bingos: Optional list of bingo words (if None, uses words of max_letters length)
            min_letters: Minimum word length
            max_letters: Maximum word length

        Returns:
            Dictionary instance

        Example:
            dict = Dictionary.from_words(
                ["CAT", "DOG", "HELLO", "WORLD"],
                bingos=["BINGOS", "PLAYER"],
                min_letters=3,
                max_letters=6
            )
        """
        d = cls(min_letters, max_letters)

        # Filter words by length
        for word in words:
            word_upper = word.upper()
            if min_letters <= len(word_upper) <= max_letters:
                d._all_words.add(word_upper)

        # Set bingos
        if bingos is None:
            d._bingos = [w for w in d._all_words if len(w) == max_letters]
        else:
            d._bingos = [b.upper() for b in bingos if len(b) >= min_letters]

        return d
```

2. Create dictionary test helpers:
```python
# tests/fixtures/dictionary_helpers.py
"""Test helpers for dictionary creation and management."""
from core.dictionary import Dictionary


def create_test_dictionary(words: List[str], **kwargs) -> Dictionary:
    """Create a minimal test dictionary.

    Args:
        words: List of valid words
        **kwargs: Additional arguments for Dictionary.from_words

    Returns:
        Dictionary instance ready for testing
    """
    return Dictionary.from_words(words, **kwargs)


# Common test dictionaries
MINIMAL_DICT = ["CAT", "DOG", "BIRD"]
SCORING_DICT = ["CAT", "FOUR", "FIVES", "SIXLET"]  # 3, 4, 5, 6 letter words
VALIDATION_DICT = ["HELLO", "WORLD", "TEST"]
```

3. Refactor tests to use in-memory dictionaries:
```python
# BEFORE (test_word_validation.py:40-49)
@async_test
async def test_good_guess_unique():
    custom_dict_path = "/tmp/test_good_guess.txt"
    with open(custom_dict_path, "w") as f:
        f.write("HELLO\nWORLD\n")

    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(min_letters=3, max_letters=6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    # ... rest of test ...
    os.remove(custom_dict_path)

# AFTER
@async_test
async def test_good_guess_unique():
    """Test a valid, new word guess awards points and triggers a shield."""
    game, mqtt, queue = await create_test_game()

    test_dict = Dictionary.from_words(
        words=["HELLO", "WORLD"],
        min_letters=3,
        max_letters=6
    )
    update_app_dictionary(game._app, test_dict)

    # ... rest of test (no file I/O, no cleanup) ...
```

**Acceptance Criteria:**
- [ ] `Dictionary.from_words()` method implemented and tested
- [ ] All temp file dictionary creation replaced with in-memory approach
- [ ] No `os.remove()` calls in test files
- [ ] Tests run faster (no file I/O)
- [ ] Tests can run in parallel without file conflicts

**Files Changed:** ~8 files
**Lines Removed:** ~50 lines
**Lines Added:** ~80 lines

---

## Phase 2: Production Code Testability Improvements
**Duration:** 5-6 days
**Goal:** Add test seams to production code to reduce coupling to internals

### Task 2.1: Add Test Seams for Border Color Verification
**Files to modify:**
- `hardware/cubes_interface.py`
- `hardware/cube_set_manager.py` (if separate)
- All tests checking `state.cube_set_managers[0].border_color` (~5 files)

**Implementation Steps:**

1. Add public accessor to `CubesHardwareInterface`:
```python
# In hardware/cubes_interface.py

class CubesHardwareInterface:
    # ... existing code ...

    def get_cube_set_border_color(self, cube_set_id: int) -> Optional[str]:
        """Get the current border color for a cube set.

        Args:
            cube_set_id: Cube set identifier (0 for P0/cubes 1-6, 1 for P1/cubes 11-16)

        Returns:
            Hex color string (e.g., "0x07E0" for green) or None if not set

        Raises:
            IndexError: If cube_set_id is invalid

        Note:
            Primarily for testing - allows verification of visual feedback
            without accessing internal state.
        """
        from hardware.cubes_to_game import state
        if cube_set_id < 0 or cube_set_id >= len(state.cube_set_managers):
            raise IndexError(f"Invalid cube set ID: {cube_set_id}")
        return state.cube_set_managers[cube_set_id].border_color
```

2. Add convenience method to `App`:
```python
# In core/app.py

class App:
    # ... existing code ...

    def get_player_border_color(self, player: int) -> Optional[str]:
        """Get border color for a player's cube set.

        Args:
            player: Player ID (0 or 1)

        Returns:
            Hex color string or None

        Example:
            color = app.get_player_border_color(0)
            assert color == "0x07E0"  # green for good guess
        """
        cube_set = self._player_to_cube_set.get(player, player)
        return self.hardware.get_cube_set_border_color(cube_set)
```

3. Refactor tests:
```python
# BEFORE
from hardware.cubes_to_game import state
manager = state.cube_set_managers[0]
assert manager.border_color == "0x07E0"

# AFTER
border_color = game._app.get_player_border_color(player=0)
assert border_color == "0x07E0"
```

**Acceptance Criteria:**
- [ ] `get_cube_set_border_color()` method added to `CubesHardwareInterface`
- [ ] `get_player_border_color()` convenience method added to `App`
- [ ] All direct `state.cube_set_managers` accesses replaced
- [ ] Tests no longer import `hardware.cubes_to_game.state`
- [ ] Unit tests added for new accessor methods

**Files Changed:** ~8 files
**Lines Removed:** ~25 lines
**Lines Added:** ~45 lines

---

### Task 2.2: Add Player Mapping Accessors
**Files to modify:**
- `core/app.py`
- `tests/integration/test_player_mapping.py`

**Implementation Steps:**

1. Add public accessors:
```python
# In core/app.py

class App:
    # ... existing code ...

    def get_player_cube_set_mapping(self, player: int) -> int:
        """Get the cube set assigned to a player.

        Args:
            player: Player ID (0 or 1)

        Returns:
            Cube set ID (0 for cubes 1-6, 1 for cubes 11-16)

        Example:
            cube_set = app.get_player_cube_set_mapping(0)
            assert cube_set == 0
        """
        return self._player_to_cube_set.get(player, player)

    def get_all_player_mappings(self) -> Dict[int, int]:
        """Get all player-to-cube-set mappings.

        Returns:
            Dictionary mapping player IDs to cube set IDs

        Example:
            mappings = app.get_all_player_mappings()
            assert mappings == {0: 0, 1: 1}
        """
        return self._player_to_cube_set.copy()
```

2. Refactor tests:
```python
# BEFORE
assert game._app._player_to_cube_set == {0: 0, 1: 1}
assert game._app._player_to_cube_set[0] == 0

# AFTER
assert game._app.get_all_player_mappings() == {0: 0, 1: 1}
assert game._app.get_player_cube_set_mapping(0) == 0
```

**Acceptance Criteria:**
- [ ] Public accessor methods added
- [ ] All `_player_to_cube_set` direct accesses replaced
- [ ] Tests use public API only

**Files Changed:** 2-3 files
**Lines Removed:** ~10 lines
**Lines Added:** ~30 lines

---

### Task 2.3: Injectable Time Provider
**Files to modify:**
- `game/game_state.py`
- `game/letter.py`
- `game/time_provider.py` (NEW)
- `tests/fixtures/game_factory.py`

**Implementation Steps:**

1. Create time provider interface:
```python
# game/time_provider.py
"""Time provider abstraction for testability."""
from abc import ABC, abstractmethod
import pygame


class TimeProvider(ABC):
    """Abstract time provider for game timing."""

    @abstractmethod
    def get_ticks(self) -> int:
        """Get current time in milliseconds.

        Returns:
            Milliseconds since initialization
        """
        pass

    @abstractmethod
    def get_seconds(self) -> float:
        """Get current time in seconds.

        Returns:
            Seconds since initialization
        """
        pass


class SystemTimeProvider(TimeProvider):
    """Production time provider using pygame clock."""

    def get_ticks(self) -> int:
        """Get current time from pygame."""
        return pygame.time.get_ticks()

    def get_seconds(self) -> float:
        """Get current time in seconds."""
        return self.get_ticks() / 1000.0


class MockTimeProvider(TimeProvider):
    """Test time provider with controllable time."""

    def __init__(self, initial_ms: int = 0):
        """Initialize with specific time.

        Args:
            initial_ms: Starting time in milliseconds
        """
        self._current_ms = initial_ms

    def get_ticks(self) -> int:
        """Get mocked time."""
        return self._current_ms

    def get_seconds(self) -> float:
        """Get mocked time in seconds."""
        return self._current_ms / 1000.0

    def advance(self, ms: int) -> None:
        """Advance time by specified milliseconds.

        Args:
            ms: Milliseconds to advance
        """
        self._current_ms += ms

    def set_time(self, ms: int) -> None:
        """Set absolute time.

        Args:
            ms: Absolute time in milliseconds
        """
        self._current_ms = ms
```

2. Update Game to use TimeProvider:
```python
# In game/game_state.py

class Game:
    def __init__(
        self,
        # ... existing params ...
        time_provider: Optional[TimeProvider] = None
    ):
        self._time = time_provider or SystemTimeProvider()
        # ... rest of init ...

    # Replace all pygame.time.get_ticks() calls:
    # OLD: now_ms = pygame.time.get_ticks()
    # NEW: now_ms = self._time.get_ticks()
```

3. Update test factory:
```python
# In tests/fixtures/game_factory.py

async def create_test_game(...) -> Tuple[Game, FakeMqttClient, asyncio.Queue]:
    # ... existing setup ...

    # Create mock time provider
    mock_time = MockTimeProvider(initial_ms=0)

    game = Game(
        # ... existing params ...
        time_provider=mock_time
    )

    # Store reference for test manipulation
    game._test_time_provider = mock_time

    return game, fake_mqtt, publish_queue
```

4. Simplify timing tests:
```python
# BEFORE
from tests.fixtures.game_factory import advance_seconds
await advance_seconds(game, queue, 10)  # Advances frames

# AFTER
game._test_time_provider.advance(10000)  # Direct time manipulation
await game.update(window, game._test_time_provider.get_ticks())
```

**Acceptance Criteria:**
- [ ] `TimeProvider` interface and implementations created
- [ ] `Game` accepts injectable `TimeProvider`
- [ ] All `pygame.time.get_ticks()` replaced with `self._time.get_ticks()`
- [ ] Tests can manipulate time directly
- [ ] Timing tests simplified and more reliable

**Files Changed:** 5-8 files
**Lines Removed:** ~30 lines
**Lines Added:** ~120 lines

---

### Task 2.4: Add Game End Reason Tracking
**Files to modify:**
- `game/game_state.py`
- `tests/integration/test_timed_mode.py`

**Implementation Steps:**

1. Add end reason tracking:
```python
# In game/game_state.py

from enum import Enum

class GameEndReason(Enum):
    """Reasons why a game ended."""
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"  # Timed mode duration reached
    RACK_FULL = "rack_full"  # No more room for letters
    USER_STOPPED = "user_stopped"  # Manual stop via input
    ERROR = "error"  # Game ended due to error


class Game:
    def __init__(self, ...):
        # ... existing init ...
        self.end_reason: Optional[GameEndReason] = None

    async def stop(self, now_ms: int, reason: GameEndReason = GameEndReason.USER_STOPPED):
        """Stop the game with specified reason.

        Args:
            now_ms: Current time in milliseconds
            reason: Why the game is ending
        """
        self.end_reason = reason
        # ... existing stop logic ...

    def _check_timeout(self, now_ms: int) -> bool:
        """Check if timed game has reached duration limit."""
        if self.descent_mode != "timed":
            return False

        elapsed_s = (now_ms - self.start_time_s * 1000) / 1000
        if elapsed_s >= self.timed_duration_s:
            await self.stop(now_ms, reason=GameEndReason.TIMEOUT)
            return True
        return False
```

2. Update tests:
```python
# BEFORE
await advance_seconds(game, queue, 10)
assert not game.running, "Game should have ended (timeout or rack full?)"

# AFTER
await advance_seconds(game, queue, 10)
assert not game.running
assert game.end_reason == GameEndReason.TIMEOUT
```

**Acceptance Criteria:**
- [ ] `GameEndReason` enum created
- [ ] `Game.end_reason` field added
- [ ] All `stop()` calls specify reason
- [ ] Tests verify end reason explicitly
- [ ] No more uncertain assertion messages

**Files Changed:** 3-4 files
**Lines Removed:** ~5 lines
**Lines Added:** ~40 lines

---

## Phase 3: Edge Cases & Bug Fixes
**Duration:** 4-5 days
**Goal:** Address suspicious behavior and edge cases revealed by tests

### Task 3.1: Clarify and Fix Late-Join Player Mapping
**Files to investigate:**
- `core/app.py` (player mapping logic)
- `game/game_state.py` (Game.start method)
- `hardware/cubes_to_game.py` (player started tracking)
- `tests/integration/test_player_mapping.py`

**Investigation Steps:**

1. Document current late-join flow:
```markdown
# Late Join Flow Analysis

## Current Behavior (to be verified):
1. P0 completes ABC → `started_cube_sets = [0]`
2. App.start() called → `calculate_player_mapping([0])` → `{0: 0}`
3. P0 marked as hardware-started
4. Game runs with P0 only
5. P1 completes ABC (later) → How is P1 added?

## Questions to Answer:
- Does P1's ABC completion trigger App.start() again?
- How does P1 get marked as hardware-started?
- Should late-join re-calculate mapping or append?
- What if P1 ABC completes but game already has 2 players via keyboard?

## Test Cases Needed:
1. P0 starts via ABC, P1 joins via ABC (late)
2. P0 starts via keyboard, P1 joins via ABC
3. P0+P1 start via keyboard, P0 completes ABC (should map to existing P0)
4. Invalid: P0 on Set 1, then P1 tries to use Set 1
```

2. Fix identified issues and add tests:
```python
# tests/integration/test_player_mapping.py

@async_test
async def test_late_join_preserves_mapping_clarified():
    """Verify late join correctly extends player mapping.

    Scenario: P0 starts via ABC on Set 0, then P1 starts via ABC on Set 1
    Expected: Both players correctly mapped and hardware-started
    """
    game, mqtt, queue = await create_test_game(player_count=1)

    # P0 starts via ABC
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.add_started_cube_set(0)
    await game._app.start(1000)

    assert game._app.get_player_cube_set_mapping(0) == 0
    assert game._app.hardware.has_player_started_game(0)
    assert not game._app.hardware.has_player_started_game(1)

    # P1 joins late via ABC
    cubes_to_game.add_started_cube_set(1)
    # Simulate the late-join trigger (TBD based on investigation)
    # Option A: Call app.start() again (idempotent?)
    # Option B: Call app.add_late_player(1, cube_set=1)
    # Option C: Late join happens automatically in next update cycle

    # After late join completes:
    assert game._app.get_player_cube_set_mapping(1) == 1
    assert game._app.hardware.has_player_started_game(1)
    assert game._app.player_count == 2


@async_test
async def test_late_join_via_keyboard_after_abc():
    """Verify keyboard join works after ABC start."""
    # ... test implementation ...


@async_test
async def test_simultaneous_abc_deterministic_mapping():
    """Verify both players starting simultaneously have deterministic mapping."""
    # ... test implementation ...
```

**Acceptance Criteria:**
- [ ] Late-join flow documented and understood
- [ ] Any bugs in late-join logic fixed
- [ ] `test_late_join_preserves_mapping` has clear assertions (no confused comments)
- [ ] At least 3 late-join scenarios tested explicitly
- [ ] Late-join works correctly in manual testing

**Files Changed:** 3-5 files
**Lines Added:** ~100-150 lines

---

### Task 3.2: Investigate and Fix Yellow Line in Discrete Mode
**Files to investigate:**
- `game/game_state.py`
- `game/position_tracker.py`
- `tests/integration/test_game_modes.py`

**Investigation Steps:**

1. Trace yellow line usage:
```bash
# Find all references to yellow_tracker and yellow_source
grep -r "yellow_tracker" --include="*.py" game/
grep -r "yellow_source" --include="*.py" game/
```

2. Decision matrix:
```markdown
# Yellow Line Decision

## Option A: Remove Yellow Line from Discrete Mode (RECOMMENDED)
- Simpler code
- Eliminates "legacy requirement" technical debt
- Clear separation of concerns

Changes needed:
- Make yellow_tracker/yellow_source Optional
- Only initialize in timed mode
- Add null checks in draw/update methods
- Update tests to verify None in discrete mode

## Option B: Keep Yellow Line but Clarify Purpose
- Document why it exists in discrete mode
- Add clear comments explaining the "legacy requirement"
- Verify it doesn't affect gameplay

## Decision: [TBD after investigation]
```

3. Implement chosen option:
```python
# If Option A chosen:

class Game:
    def __init__(self, ...):
        # ... existing code ...

        # Yellow line only exists in timed mode
        if self.descent_mode == "timed":
            self.yellow_source = YellowSource(...)
            self.yellow_tracker = PositionTracker(...)
        else:
            self.yellow_source = None
            self.yellow_tracker = None

    def draw(self, window):
        # ... existing code ...

        # Only draw yellow line if it exists
        if self.yellow_tracker is not None:
            self.yellow_tracker.draw(window)
```

4. Update tests:
```python
# BEFORE
def test_discrete_mode_has_yellow_line_hidden():
    """Verify that yellow line exists in discrete mode (legacy requirement)."""
    game, mqtt, queue = await create_test_game(player_count=1)
    assert game.yellow_source is not None
    assert game.yellow_tracker is not None

# AFTER (if Option A chosen)
def test_discrete_mode_no_yellow_line():
    """Verify that yellow line is not used in discrete mode."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    assert game.yellow_source is None
    assert game.yellow_tracker is None

def test_timed_mode_has_yellow_line():
    """Verify that yellow line exists in timed mode."""
    game, mqtt, queue = await create_test_game(descent_mode="timed")
    assert game.yellow_source is not None
    assert game.yellow_tracker is not None
```

**Acceptance Criteria:**
- [ ] Yellow line purpose documented or code removed
- [ ] Decision rationale recorded in commit message
- [ ] Tests updated to match new behavior
- [ ] No "legacy requirement" comments remain
- [ ] Discrete mode behavior clear and intentional

**Files Changed:** 2-4 files
**Lines Removed:** ~20-50 lines (if Option A)
**Lines Added:** ~10-20 lines

---

### Task 3.3: Fix Letter Bounce Boundary Logic
**Files to modify:**
- `game/letter.py`
- `tests/integration/test_letter_descent.py`

**Investigation Steps:**

1. Review current bounce implementation:
```python
# Find the boundary bounce logic
# Expected in Letter.update() or Letter._update_column_position()
```

2. Add defensive bounds checking:
```python
# In game/letter.py

class Letter:
    def _update_column_position(self, now_ms: int):
        """Update horizontal position with boundary checking."""
        if now_ms < self.next_column_move_time_ms:
            return

        # Move in current direction
        self.letter_ix += self.column_move_direction

        # IMPROVED: Clamp to valid range FIRST, then check for bounce
        self.letter_ix = max(0, min(self.letter_ix, game_config.MAX_LETTERS - 1))

        # Check boundaries and reverse direction if needed
        if self.letter_ix <= 0:
            self.column_move_direction = 1
            self.letter_ix = 0  # Ensure exactly at boundary
        elif self.letter_ix >= game_config.MAX_LETTERS - 1:
            self.column_move_direction = -1
            self.letter_ix = game_config.MAX_LETTERS - 1  # Ensure exactly at boundary

        self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS

        # Validate invariant
        assert 0 <= self.letter_ix < game_config.MAX_LETTERS, (
            f"Letter index out of bounds: {self.letter_ix}"
        )
```

3. Add comprehensive boundary tests:
```python
# tests/integration/test_letter_descent.py

@async_test
async def test_letter_never_exceeds_boundaries():
    """Verify letter index always stays within valid range."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.letter.start(0)

    # Run for many updates with various initial states
    test_cases = [
        (0, -1),   # Left boundary, moving left
        (0, 1),    # Left boundary, moving right
        (5, 1),    # Right boundary, moving right
        (5, -1),   # Right boundary, moving left
        (3, 0),    # Middle, no direction (edge case)
    ]

    for initial_ix, initial_dir in test_cases:
        game.letter.letter_ix = initial_ix
        game.letter.column_move_direction = initial_dir
        game.letter.next_column_move_time_ms = 0

        # Run 100 updates
        for i in range(100):
            game.letter.update(pygame.Surface((1,1)), i * 100)

            # INVARIANT: Always in bounds
            assert 0 <= game.letter.letter_ix < game_config.MAX_LETTERS, (
                f"Letter out of bounds: ix={game.letter.letter_ix}, "
                f"initial=({initial_ix}, {initial_dir}), iteration={i}"
            )
```

**Acceptance Criteria:**
- [ ] Letter index clamped to valid range
- [ ] Boundary conditions tested exhaustively
- [ ] No off-by-one errors
- [ ] Invariant assertions added to production code
- [ ] Tests verify letter never goes out of bounds

**Files Changed:** 2 files
**Lines Removed:** ~10 lines
**Lines Added:** ~30 lines

---

### Task 3.4: Add Configurable ABC Countdown for Tests
**Files to modify:**
- `hardware/cubes_to_game.py`
- `tests/constants.py`
- `tests/integration/test_abc_countdown.py`

**Implementation Steps:**

1. Make countdown duration configurable:
```python
# In hardware/cubes_to_game.py

class CubesGameState:
    def __init__(self):
        # ... existing init ...
        self._abc_countdown_duration_ms = 800  # Default

    def set_abc_countdown_duration(self, duration_ms: int):
        """Set ABC countdown duration (primarily for testing).

        Args:
            duration_ms: Countdown duration in milliseconds

        Note:
            Production default is 800ms. Tests can reduce to 0 for instant start.
        """
        self._abc_countdown_duration_ms = max(0, duration_ms)

    def get_abc_countdown_duration(self) -> int:
        """Get current ABC countdown duration."""
        return self._abc_countdown_duration_ms


async def check_countdown_completion(...):
    # OLD: hardcoded 800ms
    # if elapsed >= 800:

    # NEW: use configurable duration
    if elapsed >= state.get_abc_countdown_duration():
        # ... trigger start ...
```

2. Add module-level setter:
```python
# In hardware/cubes_to_game.py

def set_abc_countdown_delay(duration_ms: int):
    """Set ABC countdown delay for testing.

    Args:
        duration_ms: Delay in milliseconds (0 for instant)

    Example:
        # In test setup
        cubes_to_game.set_abc_countdown_delay(0)  # Instant start
    """
    state.set_abc_countdown_duration(duration_ms)
```

3. Update test utilities:
```python
# In tests/fixtures/mqtt_helpers.py

def reset_abc_test_state(game: Game, countdown_ms: int = 0) -> int:
    """Reset game and cubes_to_game state for ABC countdown testing.

    Args:
        game: Game instance to reset
        countdown_ms: ABC countdown duration (default 0 for instant start)

    Returns:
        Initial timestamp (always 0)
    """
    game.running = False
    cubes_to_game.set_game_running(False)
    cubes_to_game.state._started_cube_sets.clear()
    cubes_to_game.set_abc_countdown_delay(countdown_ms)  # NEW
    return 0
```

4. Simplify tests:
```python
# BEFORE
ABC_COUNTDOWN_FRAMES = 50  # Magic number
await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)

# AFTER
# Tests use instant countdown (default)
reset_abc_test_state(game, countdown_ms=0)
await process_mqtt_queue(game, queue, mqtt, now_ms)
# No frame advancement needed - start is instant

# OR for testing countdown timing specifically:
reset_abc_test_state(game, countdown_ms=100)
await advance_milliseconds(game, queue, 100)
assert game.running
```

**Acceptance Criteria:**
- [ ] ABC countdown duration is configurable
- [ ] Tests default to instant countdown (0ms)
- [ ] Frame-counting logic removed from most tests
- [ ] One test explicitly verifies countdown timing
- [ ] Tests run faster

**Files Changed:** 4-5 files
**Lines Removed:** ~20 lines
**Lines Added:** ~50 lines

---

## Phase 4: Test Coverage & Documentation
**Duration:** 3-4 days
**Goal:** Fill coverage gaps and document refactored patterns

### Task 4.1: Add Failure Path Tests
**Files to create:**
- `tests/integration/test_error_handling.py` (NEW)
- `tests/integration/test_concurrent_operations.py` (NEW)

**Implementation Steps:**

1. Create error handling tests:
```python
# tests/integration/test_error_handling.py
"""Integration tests for error conditions and failure paths."""

@async_test
async def test_mqtt_connection_failure_during_game():
    """Verify game continues if MQTT connection fails."""
    ctx = await IntegrationTestContext.create(players=[0])

    # Simulate MQTT failure
    ctx.mqtt.set_connection_state(connected=False)

    # Game should continue running
    result = await ctx.make_guess(["0", "1"], player=0)
    assert ctx.game.running
    # Verify guess processed locally even if MQTT failed


@async_test
async def test_corrupted_rack_state_recovery():
    """Verify game recovers from corrupted rack state."""
    ctx = await IntegrationTestContext.create(players=[0])

    # Corrupt rack state
    rack = ctx.game._app.rack_manager.get_rack(0)
    rack.set_tiles([])  # Empty rack (invalid)

    # Trigger rack refresh
    await ctx.game._app.load_rack(1000)

    # Verify recovery
    assert len(rack.get_tiles()) == 6


@async_test
async def test_invalid_tile_id_in_guess():
    """Verify graceful handling of invalid tile ID."""
    ctx = await IntegrationTestContext.create(players=[0])

    # Attempt guess with non-existent tile
    result = await ctx.make_guess(["999"], player=0)

    # Should not crash
    assert ctx.game.running
    assert not result.shield_created


@async_test
async def test_simultaneous_abc_from_same_player():
    """Verify duplicate ABC from same player is handled correctly."""
    game, mqtt, queue = await create_test_game()
    now_ms = reset_abc_test_state(game, countdown_ms=0)

    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"]], now_ms)

    # Trigger ABC twice rapidly
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")
    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # Immediately trigger again
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")
    await process_mqtt_queue(game, queue, mqtt, now_ms + 10)

    # Should only start once
    # Verify no duplicate player entries or crashes
    assert game.running
```

2. Create concurrent operation tests:
```python
# tests/integration/test_concurrent_operations.py
"""Tests for concurrent/simultaneous operations."""

@async_test
async def test_rapid_guess_submission():
    """Verify system handles rapid guess spam gracefully."""
    ctx = await IntegrationTestContext.create(players=[0])

    # Submit 50 guesses rapidly
    for i in range(50):
        await ctx.make_guess(["0", "1"], player=0, now_ms=i * 10)

    # Should not crash or corrupt state
    assert ctx.game.running


@async_test
async def test_simultaneous_guesses_both_players():
    """Verify both players can guess simultaneously."""
    ctx = await IntegrationTestContext.create(players=[0, 1])

    # Both players guess at same timestamp
    result_p0 = await ctx.make_guess(["0", "1"], player=0, now_ms=1000)
    result_p1 = await ctx.make_guess(["0", "1"], player=1, now_ms=1000)

    # Both should be processed independently
    assert ctx.game.running


@async_test
async def test_shield_collision_during_guess():
    """Verify shield collision during active guess doesn't corrupt state."""
    # ... implementation ...
```

**Acceptance Criteria:**
- [ ] At least 8 failure path tests added
- [ ] Error conditions tested: MQTT failure, corrupted state, invalid input
- [ ] Concurrent operations tested: rapid spam, simultaneous actions
- [ ] No crashes or hangs in failure scenarios
- [ ] Appropriate error handling verified

**Files Changed:** 2 new files
**Lines Added:** ~400 lines

---

### Task 4.2: Refactor Remaining Tests to Use New Patterns
**Files to modify:**
- All remaining integration test files not yet refactored

**Implementation Steps:**

1. Create refactoring checklist:
```markdown
# Test Refactoring Checklist

For each test file:
- [ ] Replace duplicate helpers with shared imports
- [ ] Use IntegrationTestContext where beneficial
- [ ] Use Dictionary.from_words() instead of temp files
- [ ] Use public APIs instead of _private fields
- [ ] Add clear docstrings with regression guard notes
- [ ] Remove inline debug comments (move to docs if needed)
- [ ] Verify tests still pass

Files to refactor (in order):
1. test_game_scenarios.py
2. test_single_player.py
3. test_shield_lifecycle.py
4. test_previous_guesses_display.py
5. test_cube_app_interaction.py
```

2. Refactor each file systematically

**Acceptance Criteria:**
- [ ] All test files follow new patterns
- [ ] No duplicate helper functions remain
- [ ] All tests use public APIs
- [ ] Test code volume reduced by ~20-30%
- [ ] All tests pass

**Files Changed:** ~10 files
**Lines Removed:** ~200-300 lines
**Lines Added:** ~100-150 lines

---

### Task 4.3: Documentation and Examples
**Files to create:**
- `docs/testing_guide.md` (NEW)
- `tests/README.md` (UPDATE)

**Implementation Steps:**

1. Create comprehensive testing guide:
```markdown
# Testing Guide

## Integration Test Patterns

### Using IntegrationTestContext

The `IntegrationTestContext` builder simplifies common test patterns:

```python
from tests.fixtures.test_context import IntegrationTestContext

@async_test
async def test_example():
    # Create test context with players started
    ctx = await IntegrationTestContext.create(
        players=[0, 1],
        descent_mode="discrete"
    )

    # Make guesses easily
    result = await ctx.make_guess(["0", "1"], player=0)

    # Clear assertions
    ctx.assert_border_color("0x07E0")  # green
    ctx.assert_score(player=0, expected=3)
    ctx.assert_shield_created("AB")
```

### Creating Test Dictionaries

Use in-memory dictionaries for fast, reliable tests:

```python
from core.dictionary import Dictionary
from tests.fixtures.test_helpers import update_app_dictionary

test_dict = Dictionary.from_words(
    words=["CAT", "DOG", "BIRD"],
    bingos=["PLAYER"],
    min_letters=3,
    max_letters=6
)
update_app_dictionary(game._app, test_dict)
```

### Time Manipulation

Use injectable time provider for deterministic tests:

```python
# In test
game._test_time_provider.advance(5000)  # +5 seconds
await game.update(window, game._test_time_provider.get_ticks())
```

### ABC Countdown Testing

Configure countdown duration for faster tests:

```python
from tests.fixtures.mqtt_helpers import reset_abc_test_state

# Instant start (0ms countdown)
now_ms = reset_abc_test_state(game, countdown_ms=0)
await inject_abc_sequence(mqtt, player=0)
await process_mqtt_queue(game, queue, mqtt, now_ms)
# Game starts immediately
```

## Anti-Patterns to Avoid

### ❌ Don't Access Internal State
```python
# BAD
from hardware.cubes_to_game import state
color = state.cube_set_managers[0].border_color

# GOOD
color = game._app.get_player_border_color(0)
```

### ❌ Don't Use Temp Files for Dictionaries
```python
# BAD
with open("/tmp/dict.txt", "w") as f:
    f.write("WORD\n")
dict.read("/tmp/dict.txt")
os.remove("/tmp/dict.txt")

# GOOD
dict = Dictionary.from_words(["WORD"])
```

### ❌ Don't Use Magic Numbers for Timing
```python
# BAD
await advance_frames(game, queue, frames=50)  # Why 50?

# GOOD
game._test_time_provider.advance(800)  # 800ms countdown
```

## Test Organization

### Pytest Marks

Use marks to categorize tests:
- `@pytest.mark.fast` - Runs in < 100ms
- `@pytest.mark.slow` - Runs in > 1s
- `@pytest.mark.abc` - ABC countdown tests
- `@pytest.mark.timed` - Timed mode tests
- `@pytest.mark.multiplayer` - 2-player tests

### Naming Conventions

- Test files: `test_<feature>.py`
- Test functions: `test_<behavior>_<condition>`
- Example: `test_good_guess_creates_green_border`

## Running Tests

```bash
# All integration tests
pytest tests/integration/ -v

# Fast tests only
pytest tests/integration/ -m fast

# Specific feature
pytest tests/integration/test_word_validation.py -v

# With visual mode (see pygame window)
pytest tests/integration/ -v --visual
```
```

2. Update tests/README.md with migration guide

**Acceptance Criteria:**
- [ ] Comprehensive testing guide created
- [ ] Examples provided for all new patterns
- [ ] Anti-patterns documented
- [ ] Migration guide for updating old tests
- [ ] README updated

**Files Changed:** 2 files
**Lines Added:** ~300-400 lines

---

## Phase 5: Validation and Cleanup
**Duration:** 2-3 days
**Goal:** Ensure everything works together and clean up

### Task 5.1: Full Test Suite Validation
**Steps:**

1. Run all tests with coverage:
```bash
pytest tests/integration/ -v --cov=game --cov=core --cov=hardware --cov-report=html
```

2. Check for regressions:
```bash
# Run 10 times to check for flakiness
for i in {1..10}; do
    pytest tests/integration/ -v || echo "FAILED on iteration $i"
done
```

3. Performance check:
```bash
# Measure test execution time
pytest tests/integration/ --durations=20
```

**Acceptance Criteria:**
- [ ] All tests pass consistently (10/10 runs)
- [ ] Test coverage >= 80% for modified code
- [ ] No test takes > 5 seconds (except explicitly marked slow)
- [ ] Total test suite time < 2 minutes

---

### Task 5.2: Code Review and Cleanup
**Steps:**

1. Remove dead code:
```bash
# Find unused imports
pylint tests/ --disable=all --enable=unused-import

# Find unused variables
pylint tests/ --disable=all --enable=unused-variable
```

2. Check for remaining anti-patterns:
```bash
# Find remaining temp file usage
grep -r "/tmp/" tests/integration/

# Find remaining state imports
grep -r "from hardware.cubes_to_game import state" tests/

# Find remaining _private access
grep -r "\._[a-z]" tests/integration/ | grep -v "self._" | grep -v "_app"
```

3. Format code:
```bash
black tests/
isort tests/
```

**Acceptance Criteria:**
- [ ] No dead code remains
- [ ] No temp file dictionary creation
- [ ] Minimal use of internal state access
- [ ] Code formatted consistently

---

### Task 5.3: Update CLAUDE.md with Testing Requirements
**Files to modify:**
- `CLAUDE.md`

**Implementation:**

```markdown
# Testing Requirements (add to CLAUDE.md)

## Integration Test Standards

- **CRITICAL**: Run ALL integration tests before EVERY commit: `pytest tests/integration/ -v`
- Use `IntegrationTestContext` for new integration tests
- Use `Dictionary.from_words()` for test dictionaries (no temp files)
- Access production code via public APIs only (no `._private` fields except `._app`)
- Configure ABC countdown to 0ms for test speed: `reset_abc_test_state(game, countdown_ms=0)`
- Add pytest marks: `@pytest.mark.fast`, `@pytest.mark.abc`, etc.
- Document regression guards in test docstrings

## Anti-Patterns to Avoid

- ❌ Don't import `hardware.cubes_to_game.state` directly
- ❌ Don't create temp files for dictionaries
- ❌ Don't use magic numbers for frame counts
- ❌ Don't access `_private` fields when public API exists

## Testing Guide

See `docs/testing_guide.md` for detailed patterns and examples.
```

**Acceptance Criteria:**
- [ ] CLAUDE.md updated with testing standards
- [ ] Anti-patterns documented
- [ ] Reference to testing guide added

---

## Success Metrics

### Code Quality Metrics
- [ ] Test code volume reduced by 20-30%
- [ ] Test files using public APIs: 100%
- [ ] Duplicate helpers eliminated: 100%
- [ ] Tests with clear docstrings: 100%

### Testability Metrics
- [ ] Production classes with test seams: +5 new methods
- [ ] Injectable dependencies: Time, Dictionary
- [ ] Public accessors for verification: +8 methods

### Coverage Metrics
- [ ] Failure path tests: +8 tests
- [ ] Edge case tests: +5 tests
- [ ] Integration test coverage: > 80%

### Performance Metrics
- [ ] Average test execution time: < 5 seconds
- [ ] Total suite time: < 2 minutes
- [ ] Flakiness rate: 0% (10/10 runs pass)

---

## Risk Mitigation

### Risks
1. **Breaking existing tests** - High impact, medium probability
   - Mitigation: Refactor incrementally, run tests after each change

2. **Production code changes break functionality** - High impact, low probability
   - Mitigation: Add unit tests for new public methods, manual testing

3. **Incomplete refactoring** - Medium impact, medium probability
   - Mitigation: Track progress with checklist, dedicated time blocks

### Rollback Plan
- Each phase can be rolled back independently via git
- Keep feature branches for each phase
- Merge to main only after full phase validation

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | 4-5 days | Shared utilities, TestContext, in-memory dictionaries |
| Phase 2 | 5-6 days | Test seams, time provider, game end tracking |
| Phase 3 | 4-5 days | Bug fixes, edge cases, ABC configuration |
| Phase 4 | 3-4 days | Failure tests, documentation, full refactor |
| Phase 5 | 2-3 days | Validation, cleanup, final review |
| **Total** | **18-23 days** | **~3-4 weeks** |

---

## Notes for Implementation

- Create feature branch for each phase: `refactor/phase-1-foundation`, etc.
- Commit frequently with descriptive messages
- Run full test suite after each task
- Update this plan if priorities change
- Document any deviations from the plan
