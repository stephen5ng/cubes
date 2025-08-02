#!/usr/bin/env python3

import json

# JSONL logger for MQTT publish events
publish_logger = None

def setup_publish_logger():
    """Setup JSONL logger for MQTT publish events."""
    global publish_logger
    publish_logger = open("output/output.publish.jsonl", "w")

def log_mqtt_publish(topic: str, message, retain: bool):
    """Log MQTT publish event to JSONL file."""
    if publish_logger:
        event = {
            "event_type": "mqtt_publish",
            "topic": topic,
            "message": message,
            "retain": retain
        }
        publish_logger.write(json.dumps(event) + "\n")
        publish_logger.flush()

def cleanup_publish_logger():
    """Close the MQTT publish logger."""
    global publish_logger
    if publish_logger:
        publish_logger.close()
        publish_logger = None 