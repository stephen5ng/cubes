#!/bin/bash -e

. cube_env/bin/activate
export PYTHONPATH=src:../easing-functions:../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH

# Start gameplay broker (port 1883) if needed
mqtt_server=${MQTT_SERVER:-localhost}
mosquitto_pid=""
if ! nc -zv $mqtt_server 1883 > /dev/null 2>&1; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf &
  mosquitto_pid=$!
fi

# Start control broker (port 1884) if needed
mqtt_control_server=${MQTT_CONTROL_SERVER:-localhost}
mqtt_control_port=${MQTT_CONTROL_PORT:-1884}
mosquitto_control_pid=""
if ! nc -zv $mqtt_control_server $mqtt_control_port > /dev/null 2>&1; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -p $mqtt_control_port &
  mosquitto_control_pid=$!
fi

# Clean up function that kills both mosquitto processes we started
cleanup() {
  if [ -n "$mosquitto_pid" ]; then
    kill $mosquitto_pid 2>/dev/null || true
  fi
  if [ -n "$mosquitto_control_pid" ]; then
    kill $mosquitto_control_pid 2>/dev/null || true
  fi
}

trap cleanup EXIT
./tools/delete_all_mqtt.sh

# Helper function to fetch and display final score from control broker
fetch_final_score() {
    local mqtt_control_port=${MQTT_CONTROL_PORT:-1884}

    # Use timeout to wait up to 2 seconds for the final score message
    # -C 1 means "exit after receiving 1 message"
    local score_json=$(timeout 2 mosquitto_sub -h localhost -p $mqtt_control_port -t "game/final_score" -C 1 2>/dev/null)

    if [ -n "$score_json" ]; then
        # Parse JSON and display formatted output
        echo ""
        echo "=========================================="
        echo "           FINAL SCORE"
        echo "=========================================="

        # Extract fields using python for reliable JSON parsing
        python3 -c "
import json
import sys
try:
    data = json.loads('''$score_json''')
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
" || true

        echo "=========================================="
        echo ""
    fi
}

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

# Game Loop
while true; do
    # Rebuild python arguments every iteration based on current state
    python_args=("${user_args[@]}")

    # Apply mode settings
    if [[ "$mode" == "new" ]]; then
        python_args+=("--descent-mode" "timed")
    elif [[ "$mode" == "classic" ]]; then
        # Classic mode implies legacy looping behavior
        python_args+=("--continuous")
    elif [[ "$mode" == "game_on" ]]; then
        python_args+=("--descent-mode" "timed")
        python_args+=("--stars")
        
        # Default level 0 if not specified
        level=${level:-0}
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
        else
            echo "Error: Unknown level '$level' for game_on mode. Supported levels: 0, 1, 2"
            exit 1
        fi
        
        echo "Current Level: $level"
    fi

    echo "Running game with arguments: ${python_args[@]}"
    
    set +e
    python ./main.py "${python_args[@]}"
    exit_code=$?
    set -e

    echo "Game finished with exit code: $exit_code"

    # Fetch and display final score from control broker
    fetch_final_score

    # Check if we should loop based on mode
    if [[ "$mode" == "game_on" ]]; then
        if [[ $exit_code -eq 10 ]]; then
            # Win - Advance Level
            echo "Win! Advancing level..."
            if [[ $level -lt $MAX_LEVEL ]]; then
                ((level++))
            else
                echo "Congratulations! You completed all levels!"
                break
            fi            
            continue
            
        elif [[ $exit_code -eq 11 ]]; then
            # Loss - Stay on same level
            echo "Loss! Retrying current level..."
            continue
        elif [[ $exit_code -eq 0 ]]; then
             # Normal exit (e.g. window closed or finished without special code)
             break
        else
            # Error or other exit
            break
        fi
    else
        # For classic mode, we rely on the python loop (continuous=True)
        # So if python exits, we exit.
        break
    fi
done
