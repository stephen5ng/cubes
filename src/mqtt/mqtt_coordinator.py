import asyncio
import json
import logging
import aiomqtt
from core.app import App
from game.game_state import Game
from hardware import cubes_to_game
from utils.pygameasync import events
from events.game_events import GameAbortEvent
from config.game_params import GameParams

logger = logging.getLogger(__name__)

class MQTTCoordinator:
    """Handles all MQTT message processing and routing."""

    def __init__(self, game: Game, app: App, publish_queue: asyncio.Queue, game_coordinator=None):
        self.game = game
        self.app = app
        self.publish_queue = publish_queue
        self.game_coordinator = game_coordinator

    async def handle_message(self, topic_str: str, payload, now_ms: int) -> None:
        """Route MQTT messages to appropriate handlers."""
        # logger.debug(f"{now_ms} Handling message: {topic_str} {payload}")
        if topic_str == "app/start":
            logger.info("Starting due to topic")
            await self.game.start_cubes(now_ms)

        elif topic_str == "game/start":
            logger.info("Restarting game due to control broker topic")
            # Parse payload for game parameters
            game_params = None
            if payload:
                try:
                    payload_str = payload.decode() if isinstance(payload, bytes) else payload
                    if payload_str and payload_str.strip():
                        game_params = GameParams.from_json(payload_str)
                        logger.info(f"Game params from MQTT: {game_params}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in game/start payload: {e}")

            # Store params in coordinator if provided
            if game_params and self.game_coordinator:
                self.game_coordinator.set_pending_game_params(game_params)
                # Apply params that can be updated without full recreation
                needs_re_setup = await self.game_coordinator.apply_pending_params()
                if needs_re_setup:
                    logger.info("Descent parameters changed, full re-setup would be needed")

            # Save current scores before stopping (for level progression)
            saved_scores = [score.score for score in self.game.scores] if self.game.scores else []

            # Stop the game if it's running, then restart
            if self.game.running:
                logger.info("Game is running, stopping before restart")
                await self.game.stop(now_ms, 0)

            # Reset stars display for new game
            self.game.stars_display.reset()

            # Determine the level for this game
            current_level = game_params.level if game_params else 0

            # Set baseline score BEFORE start_cubes so stars are calculated correctly
            # For level 0: baseline is 0 (fresh start)
            # For level > 0: baseline is the saved score (carry over)
            if current_level > 0 and saved_scores:
                self.game.stars_display.set_baseline_score(saved_scores[0])
                logger.info(f"Set baseline for level {current_level}: {saved_scores[0]}")
            else:
                # Level 0: baseline stays at 0 (set by reset())
                logger.info(f"Level {current_level}: baseline is 0")

            await self.game.start_cubes(now_ms)

            # Restore scores if level > 0 (preserve score across levels)
            if current_level > 0 and saved_scores:
                for i, saved_score in enumerate(saved_scores):
                    if i < len(self.game.scores):
                        self.game.scores[i].score = saved_score
                        self.game.scores[i].draw()
                logger.info(f"Restored scores for level {current_level}: {saved_scores}")

        elif topic_str == "app/abort":
            events.trigger(GameAbortEvent())

        elif topic_str == "game/guess":
            # Payload is likely string from InputManager, but let's be safe
            if isinstance(payload, bytes):
                payload_str = payload.decode()
            else:
                payload_str = payload if payload else ""
            print(f"[DEBUG] Keyboard guess: '{payload_str}' for player 1")
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

            # Log cube neighbor connections (word formation)
            sender_id = topic_str.split('/')[-1]
            neighbor_id = payload_bytes.decode() if payload_bytes else ''
            print(f"[DEBUG] Cube neighbor connection: cube {sender_id} -> cube {neighbor_id}")

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
