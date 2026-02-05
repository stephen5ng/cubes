# Control Broker Tests

## Overview

Comprehensive test suite for control broker functionality in `tests/integration/test_control_broker.py`.

## Test Coverage

### 1. `test_final_score_data_format`
**Purpose**: Verify final score data is correctly formatted and published

**What it tests**:
- Score value is correctly captured
- Stars calculation based on score and min_win_score
- Exit code correctly set to WIN (10) when score >= min_win_score
- Duration is correctly calculated from start and stop times
- All fields are present in JSON payload

**Example**:
- Score: 150, min_win_score: 100 → stars: 4 (150/(100/3) = 4.5, int=4)
- Exit code: 10 (WIN)
- Duration: 60 seconds

### 2. `test_final_score_with_no_min_win_score`
**Purpose**: Verify behavior when winning is disabled (min_win_score=0)

**What it tests**:
- Stars set to 0 when no win condition
- Exit code remains as-is (not forced to WIN)
- Score and duration still published correctly

### 3. `test_final_score_on_loss`
**Purpose**: Verify final score on game loss (exit code 11)

**What it tests**:
- Stars correctly calculated even on loss
- Exit code 11 is preserved
- Score and metrics still published

**Example**:
- Score: 50, min_win_score: 100 → stars: 1 (50/(100/3) = 1.5, int=1)

### 4. `test_final_score_uses_retain`
**Purpose**: Verify final score is published with retain=True

**What it tests**:
- Message is retained on broker
- Wrapper script can fetch it reliably
- Message persists until next game end

**Critical for console display**: Without retain=True, the message disappears before `mosquitto_sub` can retrieve it.

### 5. `test_final_score_graceful_broker_failure`
**Purpose**: Verify game doesn't crash if control broker is unavailable

**What it tests**:
- Exception handling when broker can't connect
- Game continues normally even if publish fails
- Exit code is still correctly set

**Behavior**: Error is logged but game completes successfully.

### 6. `test_final_score_connection_params`
**Purpose**: Verify correct broker connection parameters

**What it tests**:
- Client connects to `localhost` (configurable via env var)
- Client connects to port `1884` (configurable via env var)
- Default values are correct

## Test Results

✅ **6/6 control broker tests PASS**
✅ **271 total tests PASS** (150 unit + 121 integration)
✅ **No breaking changes** to existing functionality

## Running Tests

### Run only control broker tests:
```bash
python3 -m pytest tests/integration/test_control_broker.py -v
```

### Run all integration tests (includes control broker):
```bash
python3 -m pytest tests/integration/ -v
```

### Run full test suite:
```bash
python3 -m pytest tests/integration/ tests/test_*.py -v
```

## What's Not Tested

The following are tested indirectly or manually:

1. **Wrapper script integration** - Tests mock the MQTT client, so actual `mosquitto_sub` in shell script isn't tested here. Manual testing required:
   ```bash
   ./runpygame.sh --mode game_on --level 0
   ```

2. **Network latency** - Tests assume instant publish/subscribe. Real broker may have delays.

3. **Multiple brokers running** - Tests use mocks, not real brokers

4. **Environment variable configuration** - Tests use defaults, but configuration is verified in test_final_score_connection_params

## Implementation Notes

### Mock Strategy
- Used `AsyncMock` from `unittest.mock` for async function mocking
- Captured published data via `side_effect` callback
- Patched `game.game_state.aiomqtt` module

### Timing
- Tests use millisecond timestamps (now_ms) to calculate durations
- start_time_s = 100.0, stop_time_s calculated from now_ms
- Example: stop(160000ms) = 160 seconds, duration = 160 - 100 = 60s

### Error Scenarios
- Connection failures are caught and logged
- Game state is not affected by broker errors
- This ensures gameplay is never blocked by control infrastructure

## Future Test Enhancements

Potential additions:
1. Test with real brokers (integration test fixture)
2. Test message persistence/retrieval after broker restart
3. Test with slow/delayed brokers (timeout scenarios)
4. Test high-frequency score publishing
5. Functional test of wrapper script display parsing
