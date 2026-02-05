
import pytest
import asyncio
from unittest.mock import MagicMock
from pygamegameasync import BlockWordsPygame
from input.input_devices import KeyboardInput
import pygame


def test_auto_start_assigns_player_number():
    async def run_test():
        # Setup
        pygame.init() # Needed for pygame.time.get_ticks()
        
        # Mock Start Game
        async def mock_start_game(input_device, now_ms):
            return 0 # Return player 0
            
        block_words = BlockWordsPygame(
            continuous=False,  # Enable auto-start logic
            replay_file="",
            descent_mode="discrete",
            descent_duration_s=120,
            record=False,
            one_round=False,
            min_win_score=0,
            stars=False
        )
        
        # Mock dependencies
        block_words.game = MagicMock()
        block_words.game.running = False
        block_words.game.stop_time_s = 0
        block_words.game.running = False
        block_words.game.stop_time_s = 0
        
        block_words.input_controller = MagicMock()
        block_words.input_controller.start_game = MagicMock(side_effect=mock_start_game)
        
        # Mock inputs
        handlers = {}
        keyboard_input = KeyboardInput(handlers)
        input_devices = [keyboard_input]
        mqtt_queue = asyncio.Queue()
        publish_queue = asyncio.Queue()
        
        # Ensure player number is initially None
        assert keyboard_input.player_number is None
        
        # Act: Run single frame
        # We expect it to call start_game and assign the result to keyboard_input
        await block_words.run_single_frame(
            MagicMock(), # screen
            keyboard_input,
            input_devices,
            mqtt_queue,
            None, # control_message_queue
            publish_queue,
            0 # time_offset
        )
        
        # Assert
        block_words.input_controller.start_game.assert_called_once()
        assert keyboard_input.player_number == 0
        assert block_words._has_auto_started is True

    asyncio.run(run_test())
