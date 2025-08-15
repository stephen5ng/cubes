#!/usr/bin/env python3
"""
Simple MQTT Echo Responder

Responds to test/echo/* messages with test/echo/response/* 
to enable roundtrip latency measurement.
"""

import asyncio
import aiomqtt
import logging
import time

async def start_echo_responder(mqtt_server: str = "localhost"):
    """Start an MQTT echo responder service"""
    
    async with aiomqtt.Client(mqtt_server) as client:
        await client.subscribe("test/echo/#")
        
        logging.info("MQTT Echo Responder started")
        
        async for message in client.messages:
            try:
                topic = message.topic.value
                
                # Only respond to non-response echo messages
                if not topic.startswith("test/echo/response/"):
                    # Extract echo ID from topic (everything after test/echo/)
                    echo_id = topic.replace("test/echo/", "")
                    response_topic = f"test/echo/response/{echo_id}"
                    
                    # Send immediate response
                    await client.publish(response_topic, "pong", retain=False)
                    
            except Exception as e:
                logging.error(f"Echo responder error: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_echo_responder())