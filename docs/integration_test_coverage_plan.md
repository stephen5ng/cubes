# Integration Test Coverage Analysis & Plan

**Created**: 2026-01-10
**Status**: Planning Phase

## Current Test Coverage (50 tests)

### ✅ Well Covered Features

#### ABC Countdown & Game Start (4 tests)
- ✅ Both players simultaneous ABC
- ✅ Single player ABC (P0 and P1)
- ✅ Per-player ABC tracking independence
- ✅ Incomplete sequence rejection

#### Shield System (21 tests)
- ✅ Shield creation from word scoring
- ✅ Shield sizing and font scaling
- ✅ Shield animation (trajectory, velocity, acceleration)
- ✅ Shield physics (collision, bounce, blocking)
- ✅ Shield lifecycle (active→inactive, off-screen removal)
- ✅ Multiple shields independence
- ✅ Shield word in previous guesses

#### Multiplayer & Sequential Join (5 tests)
- ✅ Two-player competitive gameplay
- ✅ Independent score tracking
- ✅ Rack isolation (copy-on-write)
- ✅ Sequential player joining (P1 after P0, P0 after P1)
- ✅ Late-join rack synchronization

#### Timed Mode (3 tests)
- ✅ Yellow line descends slower than red line
- ✅ Red line pushback on shield collision
- ✅ Game ends at duration

#### Basic Gameplay (7 tests)
- ✅ Single player scoring (P0 and P1)
- ✅ Long word formation (7 letters)
- ✅ Rapid guess sequence
- ✅ Rack exhaustion
- ✅ Bingo scoring

#### Hardware Wiring (5 tests)
- ✅ Letter lock 1-player wiring
- ✅ Letter lock 2-player wiring
- ✅ Accept new letter 2-player mapping
- ✅ Load rack skips unstarted players
- ✅ Guess word keyboard player mapping

#### Input Handling (4 tests)
- ✅ Gamepad axis movement
- ✅ Gamepad button guess
- ✅ Keyboard fallback
- ✅ Rapid input handling

---

## 🔴 Missing Critical Coverage

### Priority 1: Core Game Mechanics (High Priority)

#### Letter Descent & Collision (4 tests)
**Missing**:
- [x] Letter falls at correct speed (15 seconds DROP_TIME_MS)
- [x] Letter horizontal oscillation (1 second NEXT_COLUMN_MS)
- [x] Letter column movement bounces at rack boundaries
- [x] Letter lock-on detection (2 columns away)
- [x] Letter collision with rack bottom triggers game end
- [x] Letter position resets after word accepted
- [x] Letter beeping audio scales with distance

**Why Critical**: Core game loop - letter descent is the primary mechanic

**Test File**: `test_letter_descent.py` (Implemented)

#### Word Validation & Guess Types (0 tests)
**Missing**:
- [ ] Good guess: valid word, not previously guessed → points + shield
- [ ] Old guess: valid word, already guessed → no points, yellow feedback
- [ ] Bad guess: invalid word → no points, red feedback
- [ ] Bad guess: valid word but missing letters from rack → rejected
- [ ] Minimum word length enforcement (3 letters)
- [ ] Maximum word length enforcement (6 letters)
- [ ] Dictionary lookup integration

**Why Critical**: Primary user interaction - word submission and validation

**Test File**: `test_word_validation.py` (NEW)

#### Scoring Rules (Partial coverage)
**Missing**:
- [ ] Verify word score = letter count (3-6 range)
- [ ] Bingo bonus only awarded when word uses ALL 6 tiles
- [ ] Bingo bonus = exactly +10 points
- [ ] Score cumulative across multiple words
- [ ] Old/bad guesses don't affect score

**Why Critical**: Core game rules - players need reliable scoring

**Test File**: `test_scoring_rules.py` (NEW)

---

### Priority 2: Multi-Player Edge Cases (Medium Priority)

#### Rack Management & Fair Play (1 test - incomplete)
**Missing**:
- [ ] Both players start with identical rack (fair play guarantee)
- [ ] Racks are shuffled bingo words (6 letters from SOWPODS bingos)
- [ ] Racks diverge after first different guess (copy-on-write)
- [ ] Rack tiles refresh correctly after word accepted
- [ ] New falling letter replaces correct rack position
- [ ] Rack display highlights correct tiles during guess
- [ ] Tile IDs preserved across rack operations

**Why Important**: Fair play is a core game promise

**Test File**: `test_rack_fairplay.py` (NEW)

#### Player-to-Cube-Set Mapping (1 test - incomplete)
**Missing**:
- [ ] P0 uses cube set 0 (cubes 1-6)
- [ ] P1 uses cube set 1 (cubes 11-16)
- [ ] Mapping established once at game start
- [ ] Late-join preserves existing mapping
- [ ] Single player defaults to cube set 0 for P0
- [ ] Keyboard mode defaults P0 to cube set 0

**Why Important**: Hardware wiring must be deterministic

**Test File**: `test_player_cube_mapping.py` (NEW)

#### Previous Guesses Display (0 tests)
**Missing**:
- [ ] Valid guesses appear in "possible" list
- [ ] Invalid guesses appear in "remaining" list
- [ ] Guess attribution shows correct player color
- [ ] Display toggles between possible/remaining
- [ ] Guess count tracked separately per category

**Why Important**: User feedback - players need to see history

**Test File**: `test_previous_guesses_display.py` (NEW)

---

### Priority 3: Game Modes & Configurations (Medium Priority)

#### Discrete Mode vs Timed Mode (1 test)
**Missing**:
- [ ] Discrete mode: red line only moves on events (word/landing)
- [ ] Discrete mode: Y_INCREMENT steps (not continuous)
- [ ] Timed mode: continuous descent regardless of events
- [ ] Timed mode: yellow line exists, discrete mode has no yellow line
- [ ] Mode switch doesn't break game state

**Why Important**: Different gameplay experiences need validation

**Test File**: `test_game_modes.py` (NEW)

#### Game Lifecycle (0 tests)
**Missing**:
- [ ] Game start initializes all components (racks, scores, shields, letter)
- [ ] Game start clears ABC tracking for participants
- [ ] Game stop unlocks all cube letters
- [ ] Game stop clears all cube borders
- [ ] Game end plays correct sound
- [ ] Game end logs duration and final scores
- [ ] Multiple game sessions in sequence work correctly

**Why Important**: Clean state transitions prevent bugs

**Test File**: `test_game_lifecycle.py` (NEW)

---

### Priority 4: Hardware/MQTT Integration (Medium-Low Priority)

#### MQTT Message Handling (0 tests)
**Missing**:
- [ ] Neighbor report format: `cube/right/{sender}` with neighbor ID
- [ ] Neighbor persistence across frames
- [ ] Cube letter display: `cube/{id}/letter` topic
- [ ] Cube border/lock: `cube/{id}/lock` topic
- [ ] Good guess flash: tile IDs flashed with success color
- [ ] Bad guess flash: tile IDs flashed with failure color
- [ ] Old guess flash: tile IDs flashed with yellow
- [ ] Message ordering guarantees (or lack thereof)

**Why Moderate**: Existing hardware tests cover basics, but not protocol details

**Test File**: `test_mqtt_protocol.py` (NEW)

#### Cube State Synchronization (0 tests)
**Missing**:
- [ ] Load rack sends all 6 letters to correct cube set
- [ ] Accept new letter broadcasts to both cube sets in 2P mode
- [ ] Letter lock sends to correct cube based on position
- [ ] Border clear affects all cubes in set
- [ ] State persists across MQTT reconnections

**Why Moderate**: Regression guard for hardware bugs

**Test File**: `test_cube_state_sync.py` (NEW)

---

### Priority 5: Audio & UX (Low Priority)

#### Sound System (0 tests)
**Missing**:
- [ ] Game start sound plays
- [ ] Letter beeps at correct frequencies (0-10 based on distance)
- [ ] Word pronunciation sounds play per player
- [ ] Crash/ping sound on game end
- [ ] Chunk sound when letter lands
- [ ] Input sounds (add, erase, cleared, left, right)
- [ ] Sound queue handles asynchronous playback
- [ ] Inter-word delay (0.3s) enforced

**Why Low**: Audio is nice-to-have, not core to game logic

**Test File**: `test_audio_system.py` (NEW, if time permits)

#### Animation & Rendering (0 tests)
**Missing**:
- [ ] Letter source indicator animates correctly
- [ ] Red line visual position matches game state
- [ ] Yellow line visual position matches game state
- [ ] Shield rendering uses correct player colors
- [ ] Score display positions adjust for 1P vs 2P
- [ ] Rack display highlights correct tiles

**Why Low**: Visual testing is difficult in headless mode, better for manual QA

**Test File**: Skip for now (manual testing)

---

### Priority 6: Error Handling & Edge Cases (Low Priority)

#### Resilience (0 tests)
**Missing**:
- [ ] Dictionary file missing: graceful fallback
- [ ] MQTT connection lost: queue messages or fail gracefully
- [ ] Invalid tile IDs in guess: reject without crashing
- [ ] Out-of-bounds letter position: clamp or reject
- [ ] Negative scores: impossible but should be prevented
- [ ] Race conditions in concurrent MQTT messages

**Why Low**: Edge cases, less likely in normal gameplay

**Test File**: `test_error_handling.py` (NEW, if time permits)

#### Performance & Stress (0 tests)
**Missing**:
- [ ] 10+ shields active simultaneously
- [ ] 100+ rapid guesses in sequence
- [ ] High-frequency letter position updates
- [ ] Large previous guesses list (50+ entries)

**Why Low**: Performance is best tested with profiling tools

**Test File**: Skip for now (use profiling instead)

---

## 📊 Coverage Summary

| Category | Current Tests | Missing Tests | Priority |
|----------|---------------|---------------|----------|
| **Core Mechanics** | 11 | 20 | **P1 - High** |
| **Multi-Player** | 5 | 15 | **P2 - Medium** |
| **Game Modes** | 3 | 8 | **P3 - Medium** |
| **Hardware/MQTT** | 5 | 12 | **P4 - Med-Low** |
| **Audio/UX** | 0 | 8 | **P5 - Low** |
| **Error Handling** | 0 | 6 | **P6 - Low** |
| **TOTAL** | **50** | **~69** | |

---

## 🎯 Recommended Implementation Plan

### Phase 1: Core Game Mechanics (Weeks 1-2)
**Goal**: Test the fundamental game loop

1. **`test_letter_descent.py`** (NEW - 7 tests)
   - Letter falls at correct speed
   - Horizontal oscillation timing
   - Column boundary bouncing
   - Lock-on detection
   - Rack bottom collision → game end
   - Letter position reset after word
   - Beeping audio distance scaling

2. **`test_word_validation.py`** (NEW - 7 tests)
   - Good guess validation
   - Old guess detection
   - Bad guess rejection (invalid word)
   - Bad guess rejection (missing letters)
   - Min/max length enforcement
   - Dictionary integration
   - Guess feedback visual states

3. **`test_scoring_rules.py`** (NEW - 6 tests)
   - Base score = letter count
   - Bingo bonus = +10 when using all 6
   - Bingo only awarded for full rack
   - Cumulative scoring
   - Old/bad guesses don't affect score
   - Score display updates immediately

**Deliverable**: 20 new tests covering core gameplay loop

---

### Phase 2: Multi-Player Fairness & State (Weeks 3-4)
**Goal**: Validate multi-player game integrity

4. **`test_rack_fairplay.py`** (NEW - 7 tests)
   - Identical initial racks (fair play)
   - Racks are shuffled bingos
   - Copy-on-write divergence
   - Tile refresh after word
   - Letter replacement logic
   - Rack display highlighting
   - Tile ID preservation

5. **`test_player_cube_mapping.py`** (NEW - 6 tests)
   - P0 → cube set 0 mapping
   - P1 → cube set 1 mapping
   - Mapping established at start
   - Late-join preserves mapping
   - Keyboard mode defaults
   - Sorted assignment consistency

6. **`test_previous_guesses_display.py`** (NEW - 5 tests)
   - Possible guesses list
   - Remaining guesses list
   - Player color attribution
   - Toggle between views
   - Guess count tracking

**Deliverable**: 18 new tests covering multi-player fairness

---

### Phase 3: Game Modes & Lifecycle (Week 5)
**Goal**: Validate mode-specific behavior

7. **`test_game_modes.py`** (NEW - 5 tests)
   - Discrete mode event-driven descent
   - Discrete mode Y_INCREMENT steps
   - Timed mode continuous descent
   - Yellow line only in timed mode
   - Mode switching

8. **`test_game_lifecycle.py`** (NEW - 7 tests)
   - Game start initialization
   - ABC tracking cleared for participants
   - Game stop unlock/clear
   - Game end sound/logging
   - Multiple game sessions
   - Clean state transitions
   - Memory leak prevention

**Deliverable**: 12 new tests covering game modes and lifecycle

---

### Phase 4: Hardware/MQTT Details (Week 6 - Optional)
**Goal**: Comprehensive hardware integration testing

9. **`test_mqtt_protocol.py`** (NEW - 8 tests)
   - Neighbor report format
   - Cube letter display
   - Cube border/lock
   - Guess flash colors (good/bad/old)
   - Message ordering
   - Retained message handling
   - Topic subscription patterns
   - Payload format validation

10. **`test_cube_state_sync.py`** (NEW - 6 tests)
    - Load rack broadcast
    - Accept new letter broadcast
    - Letter lock targeting
    - Border clear propagation
    - State persistence
    - Synchronization after disconnect

**Deliverable**: 14 new tests covering MQTT protocol

---

### Phase 5: Audio & Error Handling (Week 7 - If Time Permits)
**Goal**: Fill remaining gaps

11. **`test_audio_system.py`** (NEW - 8 tests)
    - Game start sound
    - Letter beep frequencies
    - Word pronunciation
    - Event sounds (crash, chunk, bloop)
    - Input sounds
    - Sound queue management
    - Inter-word delay
    - Audio channel allocation

12. **`test_error_handling.py`** (NEW - 6 tests)
    - Dictionary missing fallback
    - MQTT disconnection handling
    - Invalid tile IDs
    - Out-of-bounds positions
    - Negative score prevention
    - Race condition resilience

**Deliverable**: 14 new tests covering audio and resilience

---

## 📈 Final Coverage Target

- **Current**: 50 tests
- **Phase 1**: +20 tests (70 total)
- **Phase 2**: +18 tests (88 total)
- **Phase 3**: +12 tests (100 total)
- **Phase 4**: +14 tests (114 total, optional)
- **Phase 5**: +14 tests (128 total, if time permits)

**Recommended Minimum**: 100 tests (Phases 1-3)
**Comprehensive Coverage**: 128 tests (All phases)

---

## 🚀 Next Steps

1. **Review this plan** with team/stakeholders
2. **Prioritize phases** based on risk and time
3. **Start Phase 1** with letter descent tests
4. **Iterate weekly** with test additions
5. **Update plan** as new gaps discovered

---

## 📝 Notes

- **Test execution time**: Target <60s for 100 tests (current: 50 tests in 27s)
- **CI integration**: Run full suite on every commit
- **Test markers**: Use existing markers (fast, slow, hardware, etc.)
- **Documentation**: Each test should have comprehensive docstring
- **Regression guards**: Mark tests with specific bugs they prevent

---

**Document Version**: 1.0
**Last Updated**: 2026-01-10
**Owner**: Team
