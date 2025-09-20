#!/bin/bash

# Configuration
BROKER="${MQTT_SERVER:-localhost}"
PORT=1883
TOPIC_ROOT="#"
USERNAME=""   # optional
PASSWORD=""   # optional
TIMEOUT=1     # seconds to wait for retained messages

# Optional auth
AUTH=()
if [[ -n "$USERNAME" && -n "$PASSWORD" ]]; then
    AUTH=(-u "$USERNAME" -P "$PASSWORD")
fi

echo "Scanning retained messages under topic: $TOPIC_ROOT (preserving cube/right/* topics)"

# Collect retained topics (excluding cube/right/* topics)
TOPICS=$(mosquitto_sub -h "$BROKER" -p "$PORT" "${AUTH[@]}" -v -t "$TOPIC_ROOT" -W "$TIMEOUT" | awk '{print $1}' | grep -v '^cube/right/' | sort | uniq)

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
