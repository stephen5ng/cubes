#! /usr/bin/env python

import aiomqtt
import asyncio
import os
import random

def get_lines(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
        return [line.strip() for line in lines]

    return lines

MQTT_SERVER=os.environ.get("MQTT_SERVER", "localhost")
cubes = get_lines("cube_ids.txt")
tags = get_lines("tag_ids.txt")

# cubes_to_tags = {}
TAGS_TO_CUBES = {}
cubes_to_letters = {}
cubes_to_neighbors = {}
for cube, tag in zip(cubes, tags):
    # cubes_to_tags[cube] = tag
    TAGS_TO_CUBES[tag] = cube

async def pub():
    cube_ids = get_lines("cube_ids.txt")
    tag_ids = get_lines("tag_ids.txt")
    tag_ids.append("")

    async with aiomqtt.Client(MQTT_SERVER) as client:
        await client.subscribe("cube/#")
        async for message in client.messages:
            if "letter" in str(message.topic):
                cubes_to_letters[str(message.topic).split('/')[1]] = message.payload.decode()
                print(f"letter: {message.topic}")
            elif "nfc" in str(message.topic):
                cube = str(message.topic).split('/')[2]
                neighbor = message.payload.decode()
                cubes_to_neighbors[cube] = neighbor
                print(f"msg {cube} -> {neighbor}")
            else:
                continue

            # print(f"c2l {cubes_to_letters}")
            # print(f"c2n {cubes_to_neighbortags}")

            for cube in cubes:
                print(f"{cube}", end="")
                print(f"[{cubes_to_letters.get(cube, '')}]", end="")
                if cube in cubes_to_neighbors:
                    neighbor = cubes_to_neighbors[cube]
                    neighbor_cube = TAGS_TO_CUBES.get(neighbor, "")
                    print(f"-> {neighbor},{neighbor_cube}", end="")
                    print(f"[{cubes_to_letters.get(neighbor_cube, '')}]", end="")
                print(f"")
            print("")


asyncio.run(pub())
