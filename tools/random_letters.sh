#!/bin/bash -e

HOST=192.168.8.247
CUBE_IDS="1 2 3 4 5 6 11 12 13 14 15 16"

# Use mosquitto_rr or persistent pub. Since mosquitto_pub -l only supports
# a single topic, we use python's paho-mqtt for a single persistent connection.
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

python3 -c "
import time, sys
try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit('pip install paho-mqtt')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect('$HOST', 1883, 60)
client.loop_start()

cube_ids = [int(x) for x in '$CUBE_IDS'.split()]
try:
    while True:
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            for cube_id in cube_ids:
                client.publish(f'cube/{cube_id}/letter', letter)
            print(f'letter {letter}', file=sys.stderr)
            time.sleep(0.25)
except KeyboardInterrupt:
    client.disconnect()
"
