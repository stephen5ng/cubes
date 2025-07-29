#!/bin/bash -e

. cube_env/bin/activate
export PYTHONPATH=../easing-functions:../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH
trap "kill 0" EXIT
mqtt_server=${MQTT_SERVER:-localhost}
if ! nc -zv $mqtt_server 1883 > /dev/null 2>&1; then
  /opt/homebrew/opt/mosquitto/sbin/mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf &
fi


#python -X dev -X tracemalloc=5 ./main.py "$@"
python ./main.py "$@"
