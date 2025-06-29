#!/usr/bin/env python3

import platform
import aiomqtt
import argparse
import asyncio
import datetime
import logging
import os
import pygame
import traceback

import app
import cubes_to_game
from dictionary import Dictionary
from pygameasync import events
import pygamegameasync
import tiles
import hub75

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
my_open = open

logger = logging.getLogger(__name__)

last_cube_id = None
last_cube_time = None

async def publish_tasks_in_queue(publish_client: aiomqtt.Client, queue: asyncio.Queue) -> None:
    while True:
        topic, message, retain = await queue.get()
        # Store last messages in dict if not already defined
        if not hasattr(publish_tasks_in_queue, 'last_messages'):
            publish_tasks_in_queue.last_messages = {}
            
        # Only publish if message changed
        if topic not in publish_tasks_in_queue.last_messages or publish_tasks_in_queue.last_messages[topic] != message:
            await publish_client.publish(topic, message, retain=retain)
            publish_tasks_in_queue.last_messages[topic] = message
            logger.info(f"publishing: {topic}, {message}")
            print(f"publishing: {topic}, {message}")

async def trigger_events_from_mqtt(
    subscribe_client: aiomqtt.Client, publish_queue: asyncio.Queue, block_words: pygamegameasync.BlockWordsPygame, the_app: app.App) -> None:

    global last_cube_id, last_cube_time
    try:
        async for message in subscribe_client.messages:
            logger.info(f"trigger_events_from_mqtt incoming message topic: {message.topic} {message.payload!r}")
            if message.topic.matches("cube/nfc/#"):
                now = datetime.datetime.now()
                cube_id = str(message.topic).split('/')[2]
                last_cube_time = now
                last_cube_id = cube_id
                await cubes_to_game.handle_mqtt_message(publish_queue, message)
            elif message.topic.matches("game/guess"):
                await the_app.guess_word_keyboard(message.payload.decode(), 1)
            else:
                await block_words.handle_mqtt_message(message.topic)

    except Exception as e:
        print(f"fatal error: {e}")
        traceback.print_tb(e.__traceback__)
        events.trigger("game.abort")
        raise e

async def main(args: argparse.Namespace, dictionary: Dictionary, block_words: pygamegameasync.BlockWordsPygame, keyboard_player_number: int) -> None:
    async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
        async with aiomqtt.Client(MQTT_SERVER) as publish_client:
            publish_queue: asyncio.Queue = asyncio.Queue()
            the_app = app.App(publish_queue, dictionary)
            await cubes_to_game.init(subscribe_client, args.cubes, args.tags)
            await subscribe_client.subscribe("game/guess")

            subscribe_task = asyncio.create_task(
                trigger_events_from_mqtt(subscribe_client, publish_queue, block_words, the_app),
                name="mqtt subscribe handler")
            publish_task = asyncio.create_task(publish_tasks_in_queue(publish_client, publish_queue),
                name="mqtt publish handler")

            await block_words.main(the_app, subscribe_client, args.start, args, keyboard_player_number)

            subscribe_task.cancel()
            publish_queue.shutdown()
            publish_task.cancel()

BUNDLE_TEMP_DIR = "."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", default="tag_ids.txt", type=str)
    parser.add_argument("--cubes", default="cube_ids.txt", type=str)
    parser.add_argument('--start', action=argparse.BooleanOptionalAction)
    parser.add_argument("--keyboard-player-number", default=1, type=int, help="Player number (1 or 2) that uses keyboard input")
    args = parser.parse_args()

    # logger.setLevel(logging.DEBUG)
    pygame.mixer.init(frequency=24000, size=-16, channels=2)
    hub75.init()
    dictionary = Dictionary(tiles.MIN_LETTERS, tiles.MAX_LETTERS, open=my_open)
    dictionary.read(f"{BUNDLE_TEMP_DIR}/sowpods.txt", f"{BUNDLE_TEMP_DIR}/bingos.txt")
    pygame.init()
    block_words = pygamegameasync.BlockWordsPygame()
    asyncio.run(main(args, dictionary, block_words, args.keyboard_player_number-1))
    pygame.quit()