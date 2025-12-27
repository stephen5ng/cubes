#!/bin/bash

# Check if MQTT_SERVER is set
if [ -z "$MQTT_SERVER" ]; then
    echo "Error: MQTT_SERVER environment variable is not set"
    echo "Please set it first with: export MQTT_SERVER=your_mqtt_server"
    exit 1
fi

echo "Enter words to publish (press Ctrl+C to exit):"

# Read input line by line
while IFS= read -r line; do
    # Skip empty lines
    if [ ! -z "$line" ]; then
        # Convert to uppercase
        uppercase_line=$(echo "$line" | tr '[:lower:]' '[:upper:]')
        mosquitto_pub -h "$MQTT_SERVER" -t game/guess -m "$uppercase_line"
        echo "Published: $uppercase_line"
    fi
done 