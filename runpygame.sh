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
args=()
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
      args+=("$1")
      shift
      ;;
  esac
done

# Apply mode settings
if [[ "$mode" == "new" ]]; then
    args+=("--descent-mode" "timed")
elif [[ "$mode" == "classic" ]]; then
    # Classic mode implies legacy looping behavior
    args+=("--continuous")
elif [[ "$mode" == "game_on" ]]; then
    args+=("--descent-mode" "timed")
    
    # Default level 0 if not specified
    level=${level:-0}
    
    if [[ "$level" == "0" ]]; then
        args+=("--previous-guesses-font-size" "50")
        args+=("--remaining-guesses-font-size-delta" "4")
    elif [[ "$level" == "1" ]]; then
        args+=("--previous-guesses-font-size" "40")
        args+=("--remaining-guesses-font-size-delta" "4")
    elif [[ "$level" == "2" ]]; then
        args+=("--previous-guesses-font-size" "20")
        args+=("--remaining-guesses-font-size-delta" "2")
    else
        echo "Error: Unknown level '$level' for game_on mode. Supported levels: 0, 1, 2"
        exit 1
    fi
fi

#python -X dev -X tracemalloc=5 ./main.py "${args[@]}"
python ./main.py "${args[@]}"
