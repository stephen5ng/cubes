#!/bin/bash -e

while IFS= read -r line; do
  mosquitto_pub -h $MQTT_SERVER -t "cube/$line/sleep" -m "1" --retain
#  mosquitto_pub -h localhost -t "cube/$line/sleep" -m "1" --retain
done < "cube_ids.txt"
