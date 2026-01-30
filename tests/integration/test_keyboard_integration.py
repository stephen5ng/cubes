import pytest
from tests.fixtures.game_factory import create_test_game, async_test
from input.keyboard_handler import KeyboardHandler
from input.input_devices import KeyboardInput
from input.input_controller import GameInputController

@async_test
async def test_tab_toggles_player_modes():
    """Verify TAB toggles between single and multiplayer configs."""
    game, _, _ = await create_test_game(player_count=1)
    
    # Setup dependencies
    controller = GameInputController(game)
    # KeyboardHandler requires (game, app, input_controller)
    # game._app is the App instance
    handler = KeyboardHandler(game, game._app, controller)
    inp = KeyboardInput({})
    inp.player_number = 0
    
    # Verify initial single player state
    # Single player uses player_id -1 config
    assert game.scores[0].player_config.player_id == -1 
    assert game._app.player_count == 1
    
    # Hit TAB
    await handler.handle_event("TAB", inp, 1000)
    
    # Should toggle to 2 players (config 0)
    assert game._app.player_count == 2
    # Player 0 should now use config with ID 0
    assert game.scores[0].player_config.player_id == 0 
    
    # Hit TAB again
    await handler.handle_event("TAB", inp, 2000)
    
    # Should toggle back to 1 player settings
    assert game._app.player_count == 1
    assert game.scores[0].player_config.player_id == -1
