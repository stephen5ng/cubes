
import pytest
import asyncio
import pygame
from core import tiles
from input.input_controller import GameInputController
from game.game_state import Game
from input.input_devices import GamepadInput, KeyboardInput, InputDevice
from tests.fixtures.game_factory import create_test_game, async_test

# Replicating logic from BlockWordsPygame to test input handling mechanics

@async_test
async def test_gamepad_axis_movement():
    """Verify Joystick axis motion moves the rack cursor."""
    game, _, _ = await create_test_game()
    # Reset running state to allow proper start
    game.running = False
    

    handler = GameInputController(game)
    handlers = handler.get_handlers()
    
    gamepad = GamepadInput(handlers)
    
    # Start game for player 0
    await game.start(gamepad, 0)
    gamepad.player_number = 0 
    
    # Initial position
    assert game.racks[0].cursor_position == 0
    
    # Move Right
    event_right = {"type": "JOYAXISMOTION", "axis": 0, "value": 1.0}
    await gamepad.process_event(event_right, 0)
    assert game.racks[0].cursor_position == 1
    
    # Move Left
    event_left = {"type": "JOYAXISMOTION", "axis": 0, "value": -1.0}
    await gamepad.process_event(event_left, 0)
    assert game.racks[0].cursor_position == 0

@async_test
async def test_gamepad_button_guess():
    """Verify Joystick button press triggers a guess update (via action/space handler)."""
    game, _, _ = await create_test_game()
    game.running = False
    

    handler = GameInputController(game)
    handlers = handler.get_handlers()
    gamepad = GamepadInput(handlers)
    await game.start(gamepad, 0)
    gamepad.player_number = 0
    
    # Wait for visual rack to populate
    from tests.fixtures.game_factory import run_until_condition
    await run_until_condition(game, _, lambda: len(game.racks[0].letters()) > 0)
    
    # Sync visual rack
    tiles_list = game.racks[0].letters()
    assert len(tiles_list) > 0
    first_letter = tiles_list[0]
    
    # Press Action Button (Button 1)
    event_action = {"type": "JOYBUTTONDOWN", "button": 1}
    await gamepad.process_event(event_action, 0)
    
    # Assert guess was updated
    assert gamepad.current_guess == first_letter
    # Verify app received it (mocked/state check)
    assert game.guesses_manager.guess_to_player == {} # Not submitted yet

@async_test
async def test_keyboard_fallback():
    """Verify Keyboard logic updates input state."""
    game, _, _ = await create_test_game()
    game.running = False
    
    keyboard_input = KeyboardInput({})
    keyboard_input.player_number = 0
    await game.start(keyboard_input, 0)
    
    # Wait for visual rack
    from tests.fixtures.game_factory import run_until_condition
    await run_until_condition(game, _, lambda: len(game.racks[0].letters()) > 0)
    
    # Inject 'A' into rack
    core_rack = game._app.rack_manager.get_rack(0)
    current_tiles = core_rack.get_tiles()
    
    # Modify the first tile to be 'A'
    if current_tiles:
        current_tiles[0].letter = "A"
        await game.update_rack(current_tiles, 0, 0, 0, 0)
    
    key = "A"
    
    # Logic from BlockWordsPygame.handle_keyboard_event
    remaining_letters = list(game.racks[0].letters())
    if key in remaining_letters:
        keyboard_input.current_guess += key
        await game._app.guess_word_keyboard(keyboard_input.current_guess, 0, 0)
        
    assert keyboard_input.current_guess == "A"

@async_test
async def test_rapid_input_handling():
    """Verify stability under high-frequency input."""
    game, _, _ = await create_test_game()
    game.running = False
    

    handler = GameInputController(game)
    handlers = handler.get_handlers()
    gamepad = GamepadInput(handlers)
    await game.start(gamepad, 0)
    gamepad.player_number = 0
    
    # Spam 100 events
    for i in range(100):
        # Alternate left/right
        value = 1.0 if i % 2 == 0 else -1.0
        event = {"type": "JOYAXISMOTION", "axis": 0, "value": value}
        await gamepad.process_event(event, i * 10) 
        
    assert game.running
    # Cursor should be oscillating, just checking it didn't crash
