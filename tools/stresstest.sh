#!/bin/bash -ex
. cube_env/bin/activate

trap "kill 0" EXIT

duration="${1:-0.1}"
# Use existing MQTT_SERVER or default to localhost
export MQTT_SERVER="${MQTT_SERVER:-localhost}"

#python scripts/utilities/fake_tile_sequences.py --duration $duration --player 2 &
mosquitto_pub -h $MQTT_SERVER -t cube/right/1 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/2 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/3 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/4 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/5 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/6 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/7 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/8 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/9 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/10 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/11 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/right/12 -r -m "-"

python scripts/utilities/fake_tile_sequences.py --duration $duration --player 1 &
python start_game.py &

./runpygame.sh --descent-mode hybrid
