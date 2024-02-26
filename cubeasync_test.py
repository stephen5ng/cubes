#!/usr/bin/env python3

import asyncio
import re
from cube_async import wait_for_game_updates, listen_for_new_tiles

# Ensure that messages are handled asynchronously and correctly.

all_messages = []
update_count = 0
def handle_serial_update(message):
    global update_count
    print(f"<-- SERIAL {update_count}: {message}")
    match = re.search(r"(\d+)", message).group(1)
    if int(match) != update_count:
        raise Exception(f"incorrect serial message: {message}")
    all_messages.append("SERIAL")
    update_count += 1
    if update_count >= 10:
        return False
    return True

response_count = 0
def handle_tile(response):
    global response_count
    print(f"<-- HTTP: {response_count} {response}")
    if response["0"] != chr(ord("A") + response_count):
        raise Exception(f"incorrect http message: {response}")
    all_messages.append("HTTP")
    response_count += 1
    if response_count >= 10:
        return False
    return True


async def main():
    url = "http://localhost:8080/get_tiles"
    await asyncio.gather(wait_for_game_updates(handle_serial_update),
        listen_for_new_tiles(url, handle_tile))
    # await asyncio.gather(wait_for_game_updates(handle_serial_update))
    # await asyncio.gather(listen_for_new_tiles(url, handle_tile))
    print(all_messages)
    first_half = set(all_messages[:10])
    if len(first_half) != 2:
        raise Exception("Error: not async")

if __name__ == "__main__":
    asyncio.run(main())
