#!/usr/bin/env python3

import aiomqtt
import asyncio
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTMonitor:
    def __init__(self, mqtt_server):
        self.mqtt_server = mqtt_server
        self.last_value = None
        self.letters = ['C', 'A', 'R', 'A', 'I', 'S']
        self.cube_ids = [11, 12, 13, 14, 15, 16]
        self.waiting_for_return = False
        self.done = False

    async def run(self):
        logger.info(f"Connecting to MQTT server: {self.mqtt_server}")

        async with aiomqtt.Client(hostname=self.mqtt_server) as client:
            # Publish "*" to all cubes on startup
            logger.info("Publishing '*' to all cubes on startup...")
            await self.publish_sequence(client, ['*'] * 6)

            await client.subscribe("cube/right/14")
            logger.info("Subscribed to cube/right/14")

            async for message in client.messages:
                payload = message.payload.decode()
                logger.info(f"Received: {payload}")

                # Skip processing if we're done
                if self.done:
                    continue

                # Check for transition from "15" to "-"
                if self.last_value == "15" and payload == "-" and not self.waiting_for_return:
                    logger.info("Detected transition from '15' to '-', publishing letters...")
                    await self.publish_letters(client)
                    self.waiting_for_return = True
                    logger.info("Now waiting for cube 14 to return to '15'...")

                # Check for transition back to "15" after publishing letters
                elif self.waiting_for_return and payload == "15":
                    logger.info("Detected return to '15', publishing MAGIC!...")
                    await self.publish_magic(client)
                    self.done = True
                    logger.info("Sequence complete. No further transitions will be processed.")

                self.last_value = payload

    async def publish_sequence(self, client, letters):
        for i, (cube_id, letter) in enumerate(zip(self.cube_ids, letters)):
            topic = f"cube/{cube_id}/letter"
            logger.info(f"Publishing '{letter}' to {topic}")
            await client.publish(topic, letter, retain=True)

            # Small delay between publishes
            await asyncio.sleep(0.1)

    async def publish_letters(self, client):
        await self.publish_sequence(client, self.letters)

    async def publish_magic(self, client):
        magic_letters = ['M', 'A', 'G', 'I', 'C', '!']
        await self.publish_sequence(client, magic_letters)

async def main():
    mqtt_server = os.getenv('MQTT_SERVER', '192.168.8.247')
    monitor = MQTTMonitor(mqtt_server)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())