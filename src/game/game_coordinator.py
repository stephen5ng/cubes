
import asyncio
import pygame
import pygame.freetype
import aiomqtt
import logging

from core import app
from utils.pygameasync import Clock, events
from systems.sound_manager import SoundManager
from rendering.metrics import RackMetrics
from game.recorder import FileSystemRecorder, NullRecorder
from game.descent_strategy import DescentStrategy
from game.game_state import Game
from game.letter import Letter
from input.input_controller import GameInputController
from mqtt.mqtt_coordinator import MQTTCoordinator
from input.input_devices import (
    KeyboardInput, GamepadInput, JOYSTICK_NAMES_TO_INPUTS
)
from input.keyboard_handler import KeyboardHandler
from testing.mock_mqtt_client import MockMqttClient
from config.game_config import (
    SCREEN_WIDTH, SCREEN_HEIGHT
)

logger = logging.getLogger(__name__)

class GameCoordinator:
    """Manages game setup, initialization, and lifecycle."""

    def __init__(self):
        self.game = None
        self.mqtt_coordinator = None
        self.input_controller = None
        self.keyboard_handler = None

    def get_mock_mqtt_client(self, input_manager, replay_file, descent_mode, descent_duration_s):
        """Get the mock MQTT client for replay mode."""
        mock_mqtt_client = None
        if replay_file:
            # Replayer is already initialized in InputManager
            replayer = input_manager.replayer
            if replayer:
                # Override settings from replay metadata if available
                if replayer.descent_mode is not None:
                    descent_mode = replayer.descent_mode
                if replayer.timed_duration_s is not None:
                    descent_duration_s = replayer.timed_duration_s
                print(f"Replay config: descent_mode={descent_mode}, descent_duration_s={descent_duration_s}")
                # Create mock client with MQTT events only
                mqtt_events = [e for e in replayer.events if hasattr(e, 'mqtt')]
                mock_mqtt_client = MockMqttClient(mqtt_events)
        return mock_mqtt_client, descent_mode, descent_duration_s

    async def setup_game(self, the_app: app.App, subscribe_client: aiomqtt.Client,
                         publish_queue: asyncio.Queue, game_logger, output_logger,
                         input_manager, letter_font,
                         replay_file: str, descent_mode: str, descent_duration_s: int,
                         record: bool, one_round: bool, min_win_score: int,
                         stars: bool,
                         level: int = 0, control_client: aiomqtt.Client = None) -> tuple:
        """Set up all game components.
        
        Returns:
            tuple: (screen, keyboard_input, input_devices, mqtt_message_queue, control_message_queue, clock)
        """
        
        # Initialize MQTT coordinator
        self.mqtt_coordinator = MQTTCoordinator(None, the_app, publish_queue)  # Game injected later

        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = Clock()

        mock_mqtt_client, descent_mode, descent_duration_s = self.get_mock_mqtt_client(
            input_manager, replay_file, descent_mode, descent_duration_s
        )

        if replay_file:
            if input_manager.replayer and input_manager.replayer.events:
                 print(f"Replay mode: loaded {len(input_manager.replayer.events)} events from {replay_file}")
            mqtt_client = mock_mqtt_client
        else:
            await subscribe_client.subscribe("app/#")
            mqtt_client = subscribe_client

        # Create dependencies for injection
        sound_manager = SoundManager()
        rack_metrics = RackMetrics()

        # Get letter beeps from sound manager for injection into Game
        recorder = FileSystemRecorder() if record else NullRecorder()

        # Create strategies
        duration_ms = descent_duration_s * 1000 if descent_mode == "timed" else None
        event_descent_amount = Letter.Y_INCREMENT if descent_mode == "discrete" else 0
        descent_strategy = DescentStrategy(game_duration_ms=duration_ms, event_descent_amount=event_descent_amount)

        recovery_duration_ms = descent_duration_s * 3 * 1000
        recovery_strategy = DescentStrategy(game_duration_ms=recovery_duration_ms, event_descent_amount=0)

        self.game = Game(the_app, letter_font, game_logger, output_logger, sound_manager,
                        rack_metrics, sound_manager.get_letter_beeps(),
                        letter_strategy=descent_strategy, recovery_strategy=recovery_strategy,
                        descent_duration_s=descent_duration_s if descent_mode == "timed" else 0,
                        recorder=recorder,
                        replay_mode=bool(replay_file),
                        one_round=one_round,
                        min_win_score=min_win_score,
                        stars=stars,
                        level=level)
        self.input_controller = GameInputController(self.game)
        
        # Update coordinator with game instance
        self.mqtt_coordinator.game = self.game

        # Define handlers dictionary after dependencies are initialized
        handlers = {
            'left': self.input_controller.handle_left_movement,
            'right': self.input_controller.handle_right_movement,
            'insert': self.input_controller.handle_insert_action,
            'delete': self.input_controller.handle_delete_action,
            'action': self.input_controller.handle_space_action,
            'return': self.input_controller.handle_return_action,
            'start': self.input_controller.start_game,
        }
        
        self.keyboard_handler = KeyboardHandler(self.game, the_app, self.input_controller)

        keyboard_input = KeyboardInput(handlers)
        input_devices = [keyboard_input]
        print(f"joystick count: {pygame.joystick.get_count()}")
        if replay_file:
            input_devices.append(GamepadInput(handlers))
        elif pygame.joystick.get_count() > 0:
            for j in range(pygame.joystick.get_count()):
                joystick = pygame.joystick.Joystick(j)
                name = joystick.get_name()
                print(f"Game controller connected: {name}")
                if name in JOYSTICK_NAMES_TO_INPUTS:
                    input_device = JOYSTICK_NAMES_TO_INPUTS[name](handlers)
                    input_device.id = j
                    input_devices.append(input_device)
                else:
                    print(f"Unknown controller: {name}, skipping.")

        self.game.output_logger.start_logging()
        the_app.set_game_logger(self.game.game_logger)
        the_app.set_word_logger(self.game.output_logger)

        # Start the event engine
        await events.start()

        # Signal that the game is ready to receive MQTT messages
        if replay_file and mock_mqtt_client:
            mock_mqtt_client.set_game_ready()

        mqtt_message_queue = asyncio.Queue()
        if not replay_file:
            asyncio.create_task(self.mqtt_coordinator.process_messages_task(
                mqtt_client, mqtt_message_queue), name="mqtt processor")

        # Start control broker message processor if available
        control_message_queue = None
        if not replay_file and control_client:
            control_message_queue = asyncio.Queue()
            asyncio.create_task(self.mqtt_coordinator.process_messages_task(
                control_client, control_message_queue), name="control mqtt processor")

        return screen, keyboard_input, input_devices, mqtt_message_queue, control_message_queue, clock, descent_mode, descent_duration_s
