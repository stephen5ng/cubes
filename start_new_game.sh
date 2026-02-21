#!/bin/bash
# Start a new Blockwords game via MQTT publish
# Usage: ./start_new_game.sh [mode] [level]
#   mode: classic, new, game_on (default: classic)
#   level: 0-2 for game_on mode (default: auto)
#         If omitted, game continues from previous level (or 0 if GAME OVER)

MODE=${1:-classic}
LEVEL=${2}
MQTT_HOST=${MQTT_SERVER:-localhost}
MQTT_PORT=${MQTT_PORT:-1883}

case "$MODE" in
  classic)
    PAYLOAD=""
    ;;
  new)
    PAYLOAD='{"descent_mode":"timed","descent_duration":120}'
    ;;
  game_on)
    if [[ -z "$LEVEL" ]]; then
      # No level specified - let game continue from previous level (or 0 if GAME OVER)
      PAYLOAD='{"descent_mode":"timed","stars":true}'
    elif [[ "$LEVEL" == "0" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":90,"one_round":true,"min_win_score":50,"stars":true,"level":0}'
    elif [[ "$LEVEL" == "1" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":180,"min_win_score":90,"stars":true,"level":1}'
    elif [[ "$LEVEL" == "2" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":120,"min_win_score":360,"stars":true,"level":2}'
    else
      echo "Error: level must be 0, 1, or 2 for game_on mode"
      exit 1
    fi
    ;;
  *)
    echo "Error: mode must be 'classic', 'new', or 'game_on'"
    exit 1
    ;;
esac

echo "Starting $MODE game..."
if [[ -n "$LEVEL" ]]; then
  echo "Level: $LEVEL"
else
  echo "Level: auto (continues from previous, or 0 if GAME OVER)"
fi
if [[ -n "$PAYLOAD" ]]; then
  echo "Payload: $PAYLOAD"
fi
mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "game/start" -m "$PAYLOAD"
