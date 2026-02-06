#!/bin/bash -e

. cube_env/bin/activate
export PYTHONPATH=src:../easing-functions:../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH

# Start gameplay broker (port 1883) if needed
mqtt_server=${MQTT_SERVER:-localhost}
mosquitto_pid=""
if ! nc -z $mqtt_server 1883 2>/dev/null; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -p 1883 &
  mosquitto_pid=$!
  sleep 0.5
fi

# Start control broker (port 1884) if needed
mqtt_control_server=${MQTT_CONTROL_SERVER:-localhost}
mqtt_control_port=${MQTT_CONTROL_PORT:-1884}
mosquitto_control_pid=""
if ! nc -z $mqtt_control_server $mqtt_control_port 2>/dev/null; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -p $mqtt_control_port &
  mosquitto_control_pid=$!
  sleep 0.5
fi

# Clean up function that kills both mosquitto processes and python we started
cleanup() {
  if [ -n "$python_pid" ]; then
    kill $python_pid 2>/dev/null || true
    wait $python_pid 2>/dev/null || true
  fi
  if [ -n "$mosquitto_pid" ]; then
    kill $mosquitto_pid 2>/dev/null || true
  fi
  if [ -n "$mosquitto_control_pid" ]; then
    kill $mosquitto_control_pid 2>/dev/null || true
  fi
  # Clean up mosquitto_sub monitoring processes
  pkill -P $$ mosquitto_sub 2>/dev/null || true
}

trap cleanup EXIT
./tools/delete_all_mqtt.sh

# Parse arguments for --mode flag
user_args=()
mode="classic" # Default mode

while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)
      mode="$2"
      shift 2
      ;;
    --level)
      level="$2"
      shift 2
      ;;
    *)
      # Collect arguments intended for python script
      user_args+=("$1")
      shift
      ;;
  esac
done

MAX_LEVEL=2

# Function to build game params JSON based on mode and level
build_game_params() {
    local local_mode="$1"
    local local_level="$2"

    if [[ "$local_mode" == "new" ]]; then
        echo '{"descent_mode":"timed","descent_duration":120}'
    elif [[ "$local_mode" == "game_on" ]]; then
        local local_level=${local_level:-0}
        if [[ "$local_level" == "0" ]]; then
            echo '{"descent_mode":"timed","descent_duration":90,"one_round":true,"min_win_score":90,"stars":true,"level":0}'
        elif [[ "$local_level" == "1" ]]; then
            echo '{"descent_mode":"timed","descent_duration":180,"min_win_score":90,"stars":true,"level":1}'
        elif [[ "$local_level" == "2" ]]; then
            echo '{"descent_mode":"timed","descent_duration":120,"min_win_score":360,"stars":true,"level":2}'
        fi
    else
        # Classic mode - no special params
        echo ''
    fi
}

# Build initial python arguments
python_args=("${user_args[@]}")
if [[ "$mode" == "new" ]]; then
    python_args+=("--descent-mode" "timed")
elif [[ "$mode" == "classic" ]]; then
    python_args+=("--continuous")
elif [[ "$mode" == "game_on" ]]; then
    level=${level:-0}
    python_args+=("--descent-mode" "timed")
    python_args+=("--stars")
    python_args+=("--level" "$level")

    if [[ "$level" == "0" ]]; then
        python_args+=("--one-round")
        python_args+=("--min-win-score" "90")
        python_args+=("--descent-duration" "90")
    elif [[ "$level" == "1" ]]; then
        python_args+=("--min-win-score" "90")
        python_args+=("--descent-duration" "180")
    elif [[ "$level" == "2" ]]; then
        python_args+=("--min-win-score" "360")
        python_args+=("--descent-duration" "120")
    fi
    echo "Starting game_on mode at level: $level"
fi

echo "Running game with arguments: ${python_args[@]}"

# Start the Python game in the background
python ./main.py "${python_args[@]}" &
python_pid=$!

# Give Python a moment to start up
sleep 1

# Check if Python is still running
if ! kill -0 $python_pid 2>/dev/null; then
    echo "ERROR: Python process failed to start"
    wait $python_pid
    exit $?
fi

echo "Python game started (PID: $python_pid)"

# Monitor final_score and restart via MQTT for game_on mode
if [[ "$mode" == "game_on" ]]; then
    # Send initial game start to begin the first game
    echo "Press ESC to start the game..."

    # Monitor the final_score topic and restart accordingly
    # Use -v flag to get topic in output, format: "topic payload"
    {
        while mosquitto_sub -v -h localhost -p $mqtt_control_port -t "game/final_score" -t "game/ready" 2>/dev/null; do
            # Reconnect if connection drops
            sleep 1
        done
    } | while read -r line; do
        # Check if python process is still running
        if ! kill -0 $python_pid 2>/dev/null; then
            # Python exited, break out of monitoring
            break
        fi

        # Parse topic and payload from line (format: "topic payload")
        topic=$(echo "$line" | cut -d' ' -f1)
        payload=$(echo "$line" | cut -d' ' -f2-)

        # Check if this is a game/ready message
        if [[ "$topic" == "game/ready" ]]; then
            echo "Game ready! Starting..."
            mosquitto_pub -h localhost -p $mqtt_control_port -t "game/start" -m "$(build_game_params "game_on" "$level")"
            continue
        fi

        # Otherwise, it's a final_score message
        score_json="$payload"

        # Parse the exit code from JSON
        exit_code=$(echo "$score_json" | python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('exit_code', 0))" 2>/dev/null || echo "0")

        # Display final score
        echo ""
        echo "=========================================="
        echo "           FINAL SCORE"
        echo "=========================================="

        # Extract fields using python for reliable JSON parsing
        echo "$score_json" | python3 -c "
import json
import sys
try:
    data = json.loads(sys.stdin.read())
    print(f\"  Score:        {data.get('score', 'N/A')}\")
    print(f\"  Stars:        {data.get('stars', 'N/A')}\")
    exit_code = data.get('exit_code', 'N/A')
    result = 'Win' if exit_code == 10 else ('Loss' if exit_code == 11 else 'Quit/Abort')
    print(f\"  Result:       {result} (exit code: {exit_code})\")
    print(f\"  Duration:     {data.get('duration_s', 0):.1f}s\")
    if data.get('min_win_score', 0) > 0:
        print(f\"  Win Target:   {data.get('min_win_score', 0)}\")
except:
    pass
" 2>/dev/null || true

        echo "=========================================="
        echo ""

        # Handle win/loss/exit for game_on mode
        if [[ $exit_code -eq 10 ]]; then
            # Win - Advance Level
            echo "Win! Advancing level..."
            if [[ $level -lt $MAX_LEVEL ]]; then
                ((level++))
                echo "Current Level: $level"
                echo "Press ESC to start next level..."
            else
                echo "Congratulations! You completed all levels!"
                echo "Press ESC to play again at max level..."
            fi
        elif [[ $exit_code -eq 11 ]]; then
            # Loss - Stay on same level
            echo "Loss! Retrying current level..."
            echo "Press ESC to try again..."
        elif [[ $exit_code -eq 0 ]]; then
            # Normal exit - user quit
            echo "Game exited normally."
            break
        else
            # Error or other exit
            echo "Game exited with code: $exit_code"
            break
        fi
    done &

    # Save the monitor PID for cleanup
    monitor_pid=$!
    disown $monitor_pid 2>/dev/null || true
fi

# Wait for the Python process to finish
wait $python_pid
python_exit_code=$?

echo "Python game process exited with code: $python_exit_code"

# If python exited abnormally or user quit, we're done
cleanup
exit $python_exit_code
