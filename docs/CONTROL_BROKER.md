# Control MQTT Broker

The game now supports a second MQTT broker dedicated to overall game control and metrics, separate from the gameplay broker used for cube control.

## Purpose

- **Gameplay Broker (port 1883)**: Handles real-time cube control, letters, borders, and game messages
- **Control Broker (port 1884)**: Handles overall game control and metrics like final scores

This separation allows:
- Different systems to monitor game outcomes without interfering with gameplay
- Game metrics collection without affecting cube performance
- Independent scaling and management of control vs gameplay infrastructure

## Configuration

### Environment Variables

```bash
# Gameplay broker (default: localhost:1883)
export MQTT_SERVER=localhost
export MQTT_CLIENT_PORT=1883

# Control broker (default: localhost:1884)
export MQTT_CONTROL_SERVER=localhost
export MQTT_CONTROL_PORT=1884
```

### Configuration Files

The control broker settings are defined in `src/config/game_config.py`:

```python
MQTT_CONTROL_SERVER = os.environ.get("MQTT_CONTROL_SERVER", "localhost")
MQTT_CONTROL_PORT = int(os.environ.get("MQTT_CONTROL_PORT", "1884"))
```

## Published Messages

### `game/final_score`

Published when a game ends (win, loss, or abort). Contains:

```json
{
  "score": 150,
  "stars": 5,
  "exit_code": 10,
  "min_win_score": 90,
  "duration_s": 123.4
}
```

**Fields:**
- `score`: Final player score
- `stars`: Number of stars earned (based on min_win_score)
- `exit_code`: Exit code (10=Win, 11=Loss/one-round, 0=Normal quit, 1=Abort)
- `min_win_score`: Minimum score required to win (0 if not set)
- `duration_s`: Game duration in seconds

## Testing

### Running Both Brokers

The `runpygame.sh` script automatically:
1. Starts both brokers if they're not running
2. Runs the game
3. **Fetches and displays the final score from the control broker**
4. Continues with level progression or game loop

```bash
./runpygame.sh --mode game_on --level 0
```

After each game completes, you'll see output like:

```
Game finished with exit code: 10

==========================================
           FINAL SCORE
==========================================
  Score:        150
  Stars:        5
  Result:       Win (exit code: 10)
  Duration:     123.4s
  Win Target:   90
==========================================
```

### Manual Broker Management

Start gameplay broker:
```bash
mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf
```

Start control broker:
```bash
mosquitto -p 1884
```

### Monitoring Control Messages

**Option 1: Automatic (via runpygame.sh)**
The wrapper script automatically fetches and displays final scores after each game.

**Option 2: Live Monitoring**
Use the provided monitoring script to watch all final score messages in real-time:

```bash
./tools/monitor_control_broker.py
```

This will display final score messages as games complete (useful for monitoring multiple game instances).

**Option 3: Manual Testing**
Test the control broker independently:

```bash
# Start control broker manually
mosquitto -p 1884

# In another terminal, run the test
./test_control_broker_manual.sh
```

### Integration Tests

Integration tests use `FakeMqttClient` which doesn't require real brokers. The control broker publish will fail gracefully in tests (connection error caught and logged).

### Functional Tests

The `functional_test.py` script sets the control broker environment variables:

```python
env['MQTT_CONTROL_SERVER'] = 'localhost'
env['MQTT_CONTROL_PORT'] = '1884'
```

Ensure both brokers are running before running functional tests:

```bash
./run_functional_tests.sh
```

## Implementation Details

### Publishing Flow

1. Game ends via `Game.stop()` in `src/game/game_state.py`
2. Exit code is determined (win/loss based on score and stars)
3. Final score is published to control broker via `_publish_final_score()`
4. Connection is ephemeral - created and closed for each publish

### Error Handling

- If control broker is unavailable, the publish fails gracefully with a logged error
- Game continues normally even if control broker is down
- This ensures gameplay is never blocked by control infrastructure issues

### Code Locations

- **Configuration**: `src/config/game_config.py:70-77`
- **Publishing Logic**: `src/game/game_state.py:354-377`
- **Broker Management**: `runpygame.sh:12-29`
- **Test Environment**: `functional_test.py:22-27`
- **Monitoring Tool**: `tools/monitor_control_broker.py`

## Subscribed Messages

### `game/start`

Restart the game with optional configuration parameters. Publish to this topic to stop any running game and start a new one.

**Payload (optional JSON):**

```json
{
  "descent_mode": "timed",
  "descent_duration": 180,
  "one_round": false,
  "min_win_score": 90,
  "stars": true,
  "level": 1
}
```

**Fields:**
- `descent_mode`: Descent strategy - "discrete" (classic) or "timed" (default: "discrete")
- `descent_duration`: Duration in seconds for timed descent speed calculation (default: 120)
- `one_round`: End game after one round when true (default: false)
- `min_win_score`: Minimum score required for win condition (default: 0)
- `stars`: Show progress stars in upper right corner (default: false)
- `level`: Level number for display at start (default: 0)

**Examples:**

```bash
# Restart with default settings
mosquitto_pub -h localhost -p 1884 -t "game/start" -n

# Restart with game_on level 1 settings
mosquitto_pub -h localhost -p 1884 -t "game/start" -m '{"descent_mode":"timed","descent_duration":180,"min_win_score":90,"stars":true,"level":1}'

# Restart with game_on level 0 settings (one round)
mosquitto_pub -h localhost -p 1884 -t "game/start" -m '{"descent_mode":"timed","descent_duration":90,"one_round":true,"min_win_score":90,"stars":true,"level":0}'
```

**Parameter Mappings from runpygame.sh:**

The MQTT parameters map directly to the `runpygame.sh` flags:

| runpygame.sh flag | MQTT JSON field | Example |
|-------------------|-----------------|---------|
| `--mode new` | `descent_mode: "timed"` | `{"descent_mode":"timed"}` |
| `--mode game_on --level 0` | see level 0 example above | `{"descent_mode":"timed","descent_duration":90,"one_round":true,"min_win_score":90,"stars":true,"level":0}` |
| `--mode game_on --level 1` | `{"descent_mode":"timed","descent_duration":180,"min_win_score":90,"stars":true,"level":1}` | |
| `--mode game_on --level 2` | `{"descent_mode":"timed","descent_duration":120,"min_win_score":360,"stars":true,"level":2}` | |
| `--one-round` | `one_round: true` | |
| `--min-win-score 90` | `min_win_score: 90` | |
| `--stars` | `stars: true` | |
| `--level 1` | `level: 1` | |

## Future Extensions

Additional potential control messages:
- `game/started` - Game initialization
- `game/player_joined` - Player join events
- `game/level_completed` - Level progression
- `game/abort` - Game abort events
