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

#python -X dev -X tracemalloc=5 ./main.py "$@"
python ./main.py "$@"
