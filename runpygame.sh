#!/bin/bash -e

. cube_env/bin/activate
export PYTHONPATH=src:../easing-functions:../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH
mqtt_server=${MQTT_SERVER:-localhost}
mosquitto_pid=""
if ! nc -zv $mqtt_server 1883 > /dev/null 2>&1; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf &
  mosquitto_pid=$!
fi

# Clean up function that only kills the mosquitto process we started
cleanup() {
  if [ -n "$mosquitto_pid" ]; then
    kill $mosquitto_pid 2>/dev/null || true
  fi
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
        
        if [[ "$level" == "0" ]]; then
            python_args+=("--previous-guesses-font-size" "50")
            python_args+=("--remaining-guesses-font-size-delta" "4")
            python_args+=("--one-round")
            python_args+=("--min-win-score" "50")
            python_args+=("--descent-duration" "10") # Added based on user's implied intent
        elif [[ "$level" == "1" ]]; then
            python_args+=("--previous-guesses-font-size" "40")
            python_args+=("--remaining-guesses-font-size-delta" "4")
        elif [[ "$level" == "2" ]]; then
            python_args+=("--previous-guesses-font-size" "20")
            python_args+=("--remaining-guesses-font-size-delta" "2")
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
