import asyncio
import logging
import aiomqtt
from core.app import App
from game.game_state import Game
from hardware import cubes_to_game
from utils.pygameasync import events
from events.game_events import GameAbortEvent

logger = logging.getLogger(__name__)

class MQTTCoordinator:
    """Handles all MQTT message processing and routing."""

    def __init__(self, game: Game, app: App, publish_queue: asyncio.Queue):
        self.game = game
        self.app = app
        self.publish_queue = publish_queue

    async def handle_message(self, topic_str: str, payload, now_ms: int) -> None:
        """Route MQTT messages to appropriate handlers."""
        # logger.debug(f"{now_ms} Handling message: {topic_str} {payload}")
        if topic_str == "app/start":
            logger.info("Starting due to topic")
            await self.game.start_cubes(now_ms)

        elif topic_str == "game/start":
            logger.info("Restarting game due to control broker topic")
            # Stop the game if it's running, then restart
            if self.game.running:
                logger.info("Game is running, stopping before restart")
                await self.game.stop(now_ms, 0)
            await self.game.start_cubes(now_ms)

        elif topic_str == "app/abort":
            events.trigger(GameAbortEvent())

        elif topic_str == "game/guess":
            # Payload is likely string from InputManager, but let's be safe
            if isinstance(payload, bytes):
                payload_str = payload.decode()
            else:
                payload_str = payload if payload else ""
            await self.app.guess_word_keyboard(payload_str, 1, now_ms)

        elif topic_str.startswith("cube/right/"):
            # Reconstruct message object expected by cubes_to_game
            # cubes_to_game expects bytes payload in the message object

            payload_bytes = b''
            if payload is not None:
                if isinstance(payload, str):
                    payload_bytes = payload.encode()
                elif isinstance(payload, bytes):
                    payload_bytes = payload

            # Create a simple message-like object for cubes_to_game
            message = type('Message', (), {
                'topic': type('Topic', (), {'value': topic_str})(),
                'payload': payload_bytes
            })()

            await cubes_to_game.handle_mqtt_message(self.publish_queue, message, now_ms, self.game.sound_manager)

    async def process_messages_task(self, mqtt_client: aiomqtt.Client, message_queue: asyncio.Queue) -> None:
        """Process MQTT messages and add them to the polling queue."""
        try:
            async for message in mqtt_client.messages:
                await message_queue.put(message)
        except aiomqtt.exceptions.MqttError:
            # Expected on disconnect
            pass
        except Exception as e:
            print(f"MQTT processing error: {e}")
            events.trigger(GameAbortEvent())
            raise e
