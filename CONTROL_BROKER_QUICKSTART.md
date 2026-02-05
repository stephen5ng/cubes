# Control Broker Quick Start Guide

## What You Get

After each game, you'll automatically see:

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

## Running the Game

Just run as normal - everything is automatic:

```bash
# Classic mode
./runpygame.sh

# Game On mode with levels
./runpygame.sh --mode game_on --level 0

# New timed mode
./runpygame.sh --mode new
```

The script automatically:
- ✓ Starts gameplay broker (port 1883) if needed
- ✓ Starts control broker (port 1884) if needed
- ✓ Runs your game
- ✓ **Displays final score when game ends**
- ✓ Cleans up brokers on exit

## Monitoring Multiple Games

Want to watch scores from multiple game instances? Run the monitoring tool:

```bash
./tools/monitor_control_broker.py
```

This shows final scores from all games in real-time.

## Testing Without Playing

Test the control broker independently:

```bash
# Terminal 1: Start control broker
mosquitto -p 1884

# Terminal 2: Run test
./test_control_broker_manual.sh
```

## Configuration (Optional)

Override defaults with environment variables:

```bash
# Use a remote control broker
export MQTT_CONTROL_SERVER=192.168.1.100
export MQTT_CONTROL_PORT=1884

./runpygame.sh --mode game_on --level 0
```

## Troubleshooting

### No final score displayed?

1. Check if control broker is running:
   ```bash
   nc -zv localhost 1884
   ```

2. Manually start it:
   ```bash
   mosquitto -p 1884
   ```

3. Run game again

### Want to disable score display?

Comment out this line in `runpygame.sh`:
```bash
# fetch_final_score
```

## What's Published

The control broker receives this JSON message on `game/final_score`:

```json
{
  "score": 150,           // Final player score
  "stars": 5,             // Stars earned (based on min_win_score)
  "exit_code": 10,        // 10=Win, 11=Loss, 0=Quit, 1=Abort
  "min_win_score": 90,    // Target score to win
  "duration_s": 123.4     // Game duration in seconds
}
```

## Integration with Other Systems

The control broker can be consumed by:
- Web dashboards
- Score tracking databases
- Discord/Slack bots
- Analytics systems
- Leaderboards

Just subscribe to `game/final_score` on port 1884!

## More Information

- **Full Documentation**: `docs/CONTROL_BROKER.md`
- **Technical Details**: `CONTROL_BROKER_CHANGES.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`
