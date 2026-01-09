import asyncio
import logging
from typing import List, Optional
from testing.fake_mqtt_client import FakeMqttClient
from hardware import cubes_to_game

logger = logging.getLogger(__name__)

async def inject_neighbor_report(mqtt: FakeMqttClient, sender: str, neighbor: str):
    """Inject a neighbor report from a cube."""
    topic = f"cube/right/{sender}"
    await mqtt.inject_message(topic, neighbor)

async def simulate_abc_sequence(mqtt: FakeMqttClient, player: int = 0):
    """Simulate the A->B->C sequence to trigger game start.
    
    By default, uses cubes '1', '2', '3' for Player 0.
    """
    if player == 0:
        cubes = ['1', '2', '3']
    else:
        cubes = ['11', '12', '13']
    
    # Needs some initial neighbor reports to be "ready"
    # Actually cubes_to_game.init already sets up the mapping.
    
    # 1 touches 2
    await inject_neighbor_report(mqtt, cubes[0], cubes[1])
    # 2 touches 3
    await inject_neighbor_report(mqtt, cubes[1], cubes[2])

async def simulate_word_formation(mqtt: FakeMqttClient, word_cubes: List[str], player: int = 0):
    """Simulate cubes being placed in a chain to form a word."""
    for i in range(len(word_cubes) - 1):
        await inject_neighbor_report(mqtt, word_cubes[i], word_cubes[i+1])
    # Last cube has no neighbor to the right
    await inject_neighbor_report(mqtt, word_cubes[-1], "-")

async def inject_app_start(mqtt: FakeMqttClient):
    """Inject app/start message."""
    await mqtt.inject_message("app/start", "start")

async def process_mqtt_queue(game, publish_queue: asyncio.Queue, mqtt: FakeMqttClient, now_ms: int):
    """Process all pending MQTT messages in the fake client."""
    # This matches the logic in pygamegameasync._process_mqtt_messages and run_single_frame
    while not mqtt._message_queue.empty():
        msg = await mqtt._message_queue.get()
        topic_str = str(msg.topic)
        # Route to BlockWordsPygame.handle_mqtt_message style
        if topic_str.startswith("cube/right/"):
            await cubes_to_game.handle_mqtt_message(publish_queue, msg, now_ms, game.sound_manager)
        elif topic_str == "app/start":
            await game.start_cubes(now_ms)
        # Add more mappings as needed
