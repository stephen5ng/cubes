import pytest
from unittest.mock import MagicMock, AsyncMock
from input.keyboard_handler import KeyboardHandler
from input.input_devices import KeyboardInput
# We need game_config for MAX_PLAYERS constant
from config import game_config 

@pytest.fixture
def mock_game_setup():
    game = MagicMock()
    app = MagicMock()
    input_controller = MagicMock()
    
    # Setup common mocks
    game.toggle_player_count = MagicMock()
    # Mock racks list for letter checks
    rack = MagicMock()
    rack.letters.return_value = []
    game.racks = [rack, MagicMock()]
    
    # Mock input controller methods
    input_controller.start_game = AsyncMock(return_value=0)
    input_controller.handle_space_action = AsyncMock()
    input_controller.handle_left_movement = MagicMock()
    input_controller.handle_right_movement = MagicMock()
    input_controller.handle_return_action = MagicMock()
    
    app.guess_word_keyboard = AsyncMock()
    
    return game, app, input_controller

@pytest.mark.asyncio
async def test_tab_toggles_player_count(mock_game_setup):
    game, app, controller = mock_game_setup
    handler = KeyboardHandler(game, app, controller)
    inp = KeyboardInput({})
    inp.player_number = 0
    
    await handler.handle_event("TAB", inp, 1000)
    
    game.toggle_player_count.assert_called_once()

@pytest.mark.asyncio
async def test_escape_starts_game(mock_game_setup):
    game, app, controller = mock_game_setup
    handler = KeyboardHandler(game, app, controller)
    inp = KeyboardInput({})
    
    await handler.handle_event("ESCAPE", inp, 1000)
    
    controller.start_game.assert_awaited_once_with(inp, 1000)
    assert inp.player_number == 0
