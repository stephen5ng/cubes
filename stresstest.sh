#!/bin/bash -ex
. cube_env/bin/activate

trap "kill 0" EXIT

duration="${1:-0.1}"
export MQTT_SERVER=localhost

#python fake_tile_sequences.py --duration $duration --player 2 &
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/1 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/2 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/3 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/4 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/5 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/6 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/7 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/8 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/9 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/10 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/11 -r -m "-"
mosquitto_pub -h $MQTT_SERVER -t cube/nfc/12 -r -m "-"

python fake_tile_sequences.py --duration $duration --player 1 &
python start_game.py &

./runpygame.sh
