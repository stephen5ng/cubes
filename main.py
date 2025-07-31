#!/usr/bin/env python3

import platform
import aiomqtt
import argparse
import asyncio
import logging
import os
import pygame



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



async def publish_tasks_in_queue(publish_client: aiomqtt.Client, queue: asyncio.Queue) -> None:
    while True:
        topic, message, retain = await queue.get()
        # print(f"publish_tasks_in_queue: {topic}, {message}, {retain}")
        # Store last messages in dict if not already defined
        if not hasattr(publish_tasks_in_queue, 'last_messages'):
            publish_tasks_in_queue.last_messages = {}
            
        # Publish retained messages if they changed.
        if not retain or publish_tasks_in_queue.last_messages.get(topic, None) != message:
            # print(f"get: {publish_tasks_in_queue.last_messages.get(topic, '')}, {publish_tasks_in_queue.last_messages.get(topic, '') != message}")
            await publish_client.publish(topic, message, retain=retain)
            publish_tasks_in_queue.last_messages[topic] = message
            logger.info(f"publishing: {topic}, {message}")
            # print(f"publishing: {topic}, {message}")



async def main(args: argparse.Namespace, dictionary: Dictionary, block_words: pygamegameasync.BlockWordsPygame, keyboard_player_number: int) -> None:
    async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
        async with aiomqtt.Client(MQTT_SERVER) as publish_client:
            publish_queue: asyncio.Queue = asyncio.Queue()
            the_app = app.App(publish_queue, dictionary)
            
            await cubes_to_game.init(subscribe_client, args.tags)
            if args.replay:
                block_words.get_mock_mqtt_client()
            else:
                await subscribe_client.subscribe("game/guess")

            # MQTT subscription is now handled in pygamegameasync main loop
            publish_task = asyncio.create_task(publish_tasks_in_queue(publish_client, publish_queue),
                name="mqtt publish handler")

            await block_words.main(the_app, subscribe_client, args.start, keyboard_player_number, publish_queue)

            publish_queue.shutdown()
            publish_task.cancel()

BUNDLE_TEMP_DIR = "."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", default="tag_ids.txt", type=str)
    parser.add_argument('--start', action=argparse.BooleanOptionalAction)
    parser.add_argument("--keyboard-player-number", default=1, type=int, help="Player number (1 or 2) that uses keyboard input")
    parser.add_argument("--replay", type=str, help="Replay a game from a log file")
    args = parser.parse_args()

    # logger.setLevel(logging.DEBUG)
    pygame.mixer.init(frequency=24000, size=-16, channels=2)
    hub75.init()
    dictionary = Dictionary(tiles.MIN_LETTERS, tiles.MAX_LETTERS, open=my_open)
    dictionary.read(f"{BUNDLE_TEMP_DIR}/sowpods.txt", f"{BUNDLE_TEMP_DIR}/bingos.txt")
    pygame.init()
    block_words = pygamegameasync.BlockWordsPygame(replay_file=args.replay)
    asyncio.run(main(args, dictionary, block_words, args.keyboard_player_number-1))
    pygame.quit()