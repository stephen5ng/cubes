import pytest
from unittest.mock import MagicMock, patch
import pygame
import argparse
from config import game_config
from main import main
from pygamegameasync import BlockWordsPygame
import asyncio

class TestFontConfiguration:
    @pytest.fixture
    def mock_dependencies(self):
        with patch('main.aiomqtt.Client') as mock_mqtt, \
             patch('main.app.App') as mock_app, \
             patch('main.cubes_to_game.init') as mock_init, \
             patch('main.cubes_to_game.clear_all_letters') as mock_clear_letters, \
             patch('main.cubes_to_game.clear_all_borders') as mock_clear_borders, \
             patch('main.cubes_to_game.activate_abc_start_if_ready') as mock_activate, \
             patch('pygamegameasync.events.start') as mock_events_start, \
             patch('pygamegameasync.events.stop') as mock_events_stop, \
             patch('pygame.display.set_mode'), \
             patch('pygame.font.SysFont'), \
             patch('pygame.freetype.SysFont') as mock_freetype, \
             patch('main.Dictionary') as mock_dict, \
             patch('main.GameLogger') as mock_game_logger, \
             patch('main.PublishLogger') as mock_publish_logger, \
             patch('main.OutputLogger') as mock_output_logger, \
             patch('pygamegameasync.SoundManager') as mock_sound_manager, \
             patch('game.game_state.Score') as mock_score, \
             patch('pygamegameasync.RackMetrics') as mock_rack_metrics, \
             patch('pygame.mixer.Sound') as mock_mixer_sound, \
             patch('pygame.joystick') as mock_joystick:
             
            # Setup async mocks
            mock_mqtt.return_value.__aenter__.return_value = MagicMock()
            mock_init.return_value = asyncio.Future()
            mock_init.return_value.set_result(None)
            mock_clear_letters.return_value = asyncio.Future()
            mock_clear_letters.return_value.set_result(None)
            mock_clear_borders.return_value = asyncio.Future()
            mock_clear_borders.return_value.set_result(None)
            mock_activate.return_value = asyncio.Future()
            mock_activate.return_value.set_result(None)
            mock_events_start.return_value = asyncio.Future()
            mock_events_start.return_value.set_result(None)
            mock_events_stop.return_value = asyncio.Future()
            mock_events_stop.return_value.set_result(None)
            
            # Setup SoundManager mock
            mock_sm_instance = mock_sound_manager.return_value
            mock_sm_instance.get_letter_beeps.return_value = []
            
            # Setup Score mock
            mock_score_instance = mock_score.return_value
            mock_score_instance.get_size.return_value = (100, 20)
            
            # Setup RackMetrics mock
            mock_rm_instance = mock_rack_metrics.return_value
            mock_rm_instance.letter_width = 10
            mock_rm_instance.letter_height = 20
            mock_rm_instance.get_rect.return_value = MagicMock()
            mock_rm_instance.get_rect.return_value.x = 0
            mock_rm_instance.get_rect.return_value.y = 0
            mock_rm_instance.get_rect.return_value.width = 100
            
            # Setup RackMetrics font mock
            mock_font = MagicMock()
            mock_font.render.return_value = (MagicMock(), MagicMock())
            mock_rm_instance.font = mock_font
            
            # Setup Freetype Font mock (fallback if RackMetrics is real)
            mock_ft_font = mock_freetype.return_value
            mock_ft_font.get_rect.return_value = MagicMock()
            mock_ft_font.get_rect.return_value.size = (10, 20)
            mock_ft_font.get_rect.return_value.width = 10
            
            mock_joystick.get_count.return_value = 0
            
            yield {
                'mqtt': mock_mqtt,
                'app': mock_app,
                'dictionary': mock_dict,
                'game_logger': mock_game_logger,
                'sound_manager': mock_sound_manager,
                'rack_metrics': mock_rack_metrics,
                'freetype': mock_freetype
            }

    def test_default_font_configuration(self, mock_dependencies):
        # Arrange
        args = argparse.Namespace(
            replay=None, 
            start=False, 
            keyboard_player_number=1,
            descent_mode="discrete",
            timed_duration=120,
            record=False,
            previous_guesses_font_size=30,
            remaining_guesses_font_size_delta=game_config.FONT_SIZE_DELTA
        )
        
        # Instantiate BlockWordsPygame with default arguments logic (simulating main.py)
        block_words = BlockWordsPygame(
            previous_guesses_font_size=args.previous_guesses_font_size,
            remaining_guesses_font_size_delta=args.remaining_guesses_font_size_delta,
            replay_file="", 
            descent_mode="discrete",
            descent_duration_s=120,
            record=False,
        )
        
        
        # Act
        # Setup the game to initialize components
        mock_subscribe_client = MagicMock()
        mock_subscribe_client.subscribe.return_value = asyncio.Future()
        mock_subscribe_client.subscribe.return_value.set_result(None)
        
        asyncio.run(block_words.setup_game(
            mock_dependencies['app'], 
            mock_subscribe_client, 
            asyncio.Queue(), 
            MagicMock(), 
            MagicMock()
        ))
        
        # Assert
        assert block_words.game.previous_guesses_font_size == 30
        assert block_words.game.remaining_guesses_font_size_delta == game_config.FONT_SIZE_DELTA
        # Verify SysFont was called with correct size
        # PreviousGuessesDisplay uses "Arial" and 30
        mock_dependencies['freetype'].assert_any_call("Arial", 30)
        
        assert block_words.game.guesses_manager.font_size_delta == game_config.FONT_SIZE_DELTA

    def test_custom_font_configuration(self, mock_dependencies):
         # Arrange
        custom_font_size = 50
        custom_delta = 10
        
        args = argparse.Namespace(
            replay=None, 
            start=False, 
            keyboard_player_number=1,
            descent_mode="discrete",
            timed_duration=120,
            record=False,
            previous_guesses_font_size=custom_font_size,
            remaining_guesses_font_size_delta=custom_delta
        )
        
        # Instantiate BlockWordsPygame with custom arguments
        block_words = BlockWordsPygame(
            previous_guesses_font_size=args.previous_guesses_font_size,
            remaining_guesses_font_size_delta=args.remaining_guesses_font_size_delta,
            replay_file="", 
            descent_mode="discrete",
            descent_duration_s=120,
            record=False,
        )
        
        # Act
        mock_subscribe_client = MagicMock()
        mock_subscribe_client.subscribe.return_value = asyncio.Future()
        mock_subscribe_client.subscribe.return_value.set_result(None)

        asyncio.run(block_words.setup_game(
            mock_dependencies['app'], 
            mock_subscribe_client, 
            asyncio.Queue(), 
            MagicMock(), 
            MagicMock()
        ))
        
        # Assert
        assert block_words.game.previous_guesses_font_size == custom_font_size
        assert block_words.game.remaining_guesses_font_size_delta == custom_delta
        # Note: We can't easily check the font size of the freetype font directly if it's mocked or if accessing the size property is tricky on the mock/object,
        # but we can check the attributes on the managers.
        # However, checking block_words.game.guesses_manager.previous_guesses_display.font (mocked) should show the call.
        
        # Verify SysFont was called with correct size
        mock_dependencies['freetype'].assert_any_call("Arial", custom_font_size)
        
        # Le's inspect the Game's attributes which we know we set
        assert block_words.game.guesses_manager.font_size_delta == custom_delta
        # And check that PreviousGuessesDisplay was initialized with the correct font size
        # Since we can't easily introspect the real pygame object if we are running in a headless env without display, 
        # but we can rely on proper propogation to the manager class attributes we just added.

    def test_invalid_font_size(self, mock_dependencies):
        # Arrange
        custom_font_size = -10  # Invalid font size
        
        args = argparse.Namespace(
            replay=None, 
            start=False, 
            keyboard_player_number=1,
            descent_mode="discrete",
            timed_duration=120,
            record=False,
            previous_guesses_font_size=custom_font_size,
            remaining_guesses_font_size_delta=game_config.FONT_SIZE_DELTA
        )
        
        # Instantiate BlockWordsPygame with custom arguments
        block_words = BlockWordsPygame(
            previous_guesses_font_size=args.previous_guesses_font_size,
            remaining_guesses_font_size_delta=args.remaining_guesses_font_size_delta,
            replay_file="", 
            descent_mode="discrete",
            descent_duration_s=120,
            record=False,
        )
        
        # Act
        mock_subscribe_client = MagicMock()
        mock_subscribe_client.subscribe.return_value = asyncio.Future()
        mock_subscribe_client.subscribe.return_value.set_result(None)

        with pytest.raises(ValueError) as excinfo:
            asyncio.run(block_words.setup_game(
                mock_dependencies['app'], 
                mock_subscribe_client, 
                asyncio.Queue(), 
                MagicMock(), 
                MagicMock()
            ))
        
        # Assert
        assert "Invalid font size" in str(excinfo.value)
