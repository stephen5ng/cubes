#!/bin/bash

# Configuration
BROKER="$MQTT_SERVER"
PORT=1883
TOPIC_ROOT="#"
USERNAME=""   # optional
PASSWORD=""   # optional
TIMEOUT=5     # seconds to wait for retained messages

# Optional auth
AUTH=()
if [[ -n "$USERNAME" && -n "$PASSWORD" ]]; then
    AUTH=(-u "$USERNAME" -P "$PASSWORD")
fi

echo "Scanning retained messages under topic: $TOPIC_ROOT"

# Collect retained topics
TOPICS=$(mosquitto_sub -h "$BROKER" -p "$PORT" "${AUTH[@]}" -v -t "$TOPIC_ROOT" -W "$TIMEOUT" | awk '{print $1}' | sort | uniq)

if [[ -z "$TOPICS" ]]; then
    echo "No retained messages found."
    exit 0
fi

echo "Found retained topics:"
echo "$TOPICS"
echo "Deleting..."

# Publish empty retained messages to delete
while IFS= read -r topic; do
    mosquitto_pub -h "$BROKER" -p "$PORT" "${AUTH[@]}" -t "$topic" -r -n
    echo "Cleared retained message on topic: $topic"
done <<< "$TOPICS"

echo "Done."
