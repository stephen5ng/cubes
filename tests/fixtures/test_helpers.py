"""Shared test helper functions used across integration tests."""
import asyncio
from typing import Optional
from core.dictionary import Dictionary
from core.app import App
from testing.fake_mqtt_client import FakeMqttClient

def update_app_dictionary(app: App, new_dictionary: Dictionary) -> None:
    """Update dictionary references across all App components.

    Args:
        app: Application instance
        new_dictionary: Dictionary instance to use

    Note:
        Updates App, ScoreCard, and RackManager dictionary references
        to ensure consistency across components.
    """
    app._dictionary = new_dictionary
    app._score_card.dictionary = new_dictionary
    app.rack_manager.dictionary = new_dictionary


async def drain_mqtt_queue(mqtt: FakeMqttClient, queue: asyncio.Queue) -> None:
    """Process all pending MQTT messages from queue to client.

    Args:
        mqtt: FakeMqttClient instance
        queue: asyncio.Queue containing pending MQTT messages

    Note:
        Drains queue and publishes all messages to the fake client.
        Useful for ensuring all async MQTT operations complete before assertions.
    """
    while not queue.empty():
        item = queue.get_nowait()
        if isinstance(item, tuple):
            # (topic, payload, retain, qos/timestamp)
            topic, payload, retain, *_ = item
            await mqtt.publish(topic, payload, retain)
        else:
            await mqtt.publish(item.topic, item.payload)
