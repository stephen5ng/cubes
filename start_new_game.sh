#!/bin/bash
# Start a new Blockwords game via MQTT publish
# Usage: ./start_new_game.sh [mode] [level]
#   mode: classic, new, game_on (default: classic)
#   level: 1-3 for game_on mode (default: auto)
#         If omitted, game continues from previous level (or 1 if GAME OVER)

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
      # No level specified - let game continue from previous level (or 1 if GAME OVER)
      PAYLOAD='{"descent_mode":"timed","stars":true}'
    elif [[ "$LEVEL" == "1" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":45,"one_round":true,"min_win_score":50,"stars":true,"level":1,"next_column_ms":null,"letter_linger_ms":0,"letter_drop_time_ms":90000}'
    elif [[ "$LEVEL" == "2" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":90,"min_win_score":90,"stars":true,"level":2,"next_column_ms":1000,"letter_linger_ms":500,"letter_drop_time_ms":15000}'
    elif [[ "$LEVEL" == "3" ]]; then
      PAYLOAD='{"descent_mode":"timed","descent_duration":70,"min_win_score":360,"stars":true,"level":3,"next_column_ms":500,"letter_linger_ms":0,"letter_drop_time_ms":10000}'
    else
      echo "Error: level must be 1, 2, or 3 for game_on mode"
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
  echo "Level: auto (continues from previous, or 1 if GAME OVER)"
fi
if [[ -n "$PAYLOAD" ]]; then
  echo "Payload: $PAYLOAD"
fi
mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "game/start" -m "$PAYLOAD"
