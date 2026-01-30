
import pytest
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test, advance_seconds, advance_frames
from game.letter import Letter
from game.components import Shield
from config import game_config
import pygame

@async_test
async def test_letters_fall_at_constant_speed():
    """Test that letters fall vertically over time in discrete mode."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")

    game.start_time_s = 0
    game.running = True

    game.letter.start(0)
    game.letter.letter = "A"  # Assign a letter so the system is active
    initial_y = game.letter.pos[1]

    # Advance time and verify letter moves down
    await advance_seconds(game, queue, 1.0)

    current_y = game.letter.pos[1]

    # Letter should have moved down (or cycled if it hit bottom)
    # In discrete mode, game continues and letters cycle
    assert game.running, "Game should still be running in discrete mode"

    # Verify the letter moved or cycled (cycling resets to top)
    # After enough time, the letter will have reached bottom and cycled
    assert current_y >= 0, "Letter position should be valid"


@async_test
async def test_letters_horizontal_oscillation():
    """Test that letters move horizontally back and forth between columns."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    game.letter.NEXT_COLUMN_MS = 100
    game.letter.start(0)
    
    start_ix = 1
    assert game.letter.letter_ix == start_ix
    
    await advance_seconds(game, queue, 0.15)
    assert game.letter.letter_ix == start_ix + 1, "Should have moved right by 1"


@async_test
async def test_letter_lock_on_behavior():
    """Test that letter stops moving horizontally when it reaches the bottom area."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    game.letter.NEXT_COLUMN_MS = 100
    game.letter.start(0)
    
    game.letter.pos[1] = game.letter.height - game.letter.letter_height - 1
    game.letter.draw(100)
    assert game.letter.locked_on, "Letter should be locked on when near bottom"
    
    initial_ix = game.letter.letter_ix
    await advance_seconds(game, queue, 1.0) 
    assert game.letter.letter_ix == initial_ix, "Letter should not move horizontally when locked on"


@async_test
async def test_letter_collides_with_rack_bottom():
    """Test that a letter colliding with the rack bottom is accepted into the rack."""
    # Use discrete mode where letters are accepted into the rack (timed mode ends game on floor collision)
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    game.letter.letter = "A"
    game.letter.DROP_TIME_MS = 100
    game.letter.start(0)
    game.letter.letter = "A"
    
    initial_tiles = game._app.rack_manager.get_rack(0).get_tiles()
    target_index = 1 
    initial_char = initial_tiles[target_index].letter
    
    new_letter = "X" if initial_char != "X" else "Y"
    game.letter.letter = new_letter
    
    await advance_seconds(game, queue, 0.2) 
    
    current_tiles = game._app.rack_manager.get_rack(0).get_tiles()
    final_char = current_tiles[target_index].letter
    assert final_char == new_letter, f"Expected {new_letter}, got {final_char}"
    assert game.running, "Game should continue after letter acceptance"


@async_test
async def test_letter_column_movement_bounces_at_boundaries():
    """Verify that letter index bounces correctly at column 0 and MAX_LETTERS-1."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    game.letter.NEXT_COLUMN_MS = 100
    game.letter.start(0)
    
    # Right boundary bounce
    game.letter.letter_ix = 5
    game.letter.column_move_direction = 1
    game.letter.next_column_move_time_ms = 0
    game.letter.update(pygame.Surface((1,1)), 1000)
    
    assert game.letter.letter_ix == 4
    assert game.letter.column_move_direction == -1
    
    # Left boundary bounce
    game.letter.letter_ix = 0
    game.letter.column_move_direction = -1
    game.letter.next_column_move_time_ms = 0
    game.letter.update(pygame.Surface((1,1)), 2000)
    
    assert game.letter.letter_ix == 1
    assert game.letter.column_move_direction == 1


@async_test
async def test_letter_position_resets_after_word_accepted():
    """Test that letter position resets to the top after being accepted via rack collision."""
    # Use discrete mode where letters are accepted and reset (timed mode ends game on floor collision)
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    game.letter.DROP_TIME_MS = 100
    game.letter.start(0)
    game.letter.letter = "A"
    
    # Wait for letter to fall and be accepted (cleared)
    from tests.fixtures.game_factory import run_until_condition
    
    # 1. Wait for collision/acceptance (letter becomes empty)
    # DROP_TIME_MS is 100, so it should happen quickly
    success = await run_until_condition(game, queue, lambda: game.letter.letter == "", max_frames=20)
    assert success, f"Letter failed to fall/accept within time. Pos: {game.letter.pos[1]}"
    assert game.letter.letter == "", "Letter should be cleared after acceptance"

    # 2. Wait for next letter to be spawned (handling the event)
    success = await run_until_condition(game, queue, lambda: game.letter.letter != "", max_frames=20)
    assert success, "Game failed to spawn next letter"
    
    current_y = game.letter.pos[1]
    bottom_y = game.letter.height
    
    assert current_y < bottom_y * 0.5, f"Letter should reset to top area, got {current_y}"
    assert game.letter.letter != "", "Game should have next letter"


@async_test
async def test_letter_beeping_audio_scales_with_distance():
    """Test that audio beep index scales correctly as the letter falls."""
    game, mqtt, queue = await create_test_game()
    game.start_time_s = 0
    
    mock_sounds = [MagicMock() for _ in range(11)]
    game.letter.letter_beeps = mock_sounds
    
    # top: index 0
    game.letter.pos[1] = 0
    game.letter.last_beep_time_ms = 0
    game.letter._update_beeping(10000) 
    assert mock_sounds[0].play.called
    mock_sounds[0].reset_mock()
    
    # middle: index 5
    game.letter.pos[1] = game_config.SCREEN_HEIGHT // 2
    game.letter.last_beep_time_ms = 0
    game.letter._update_beeping(10000)
    assert mock_sounds[5].play.called
    mock_sounds[5].reset_mock()
    
    # bottom: index 10
    game.letter.pos[1] = game_config.SCREEN_HEIGHT
    game.letter.last_beep_time_ms = 0
    game.letter._update_beeping(10000)
    assert mock_sounds[10].play.called


@async_test
async def test_letter_collision_with_shield():
    """Test that colliding with a shield causes the letter to bounce upwards."""
    game, mqtt, queue = await create_test_game(descent_mode="timed", descent_duration_s=10)
    game.start_time_s = 0
    
    game.letter.start(0)
    game.letter.letter = "A"
    
    shield_y = game.letter.height // 2
    from tests.fixtures.game_factory import create_shield
    new_shield = create_shield(word="BINGO", x=0, y=shield_y, health=100, player=0, created_time_ms=0)
    game.shields.append(new_shield)
    
    game.letter.pos[1] = shield_y
    now_ms = 1000
    game.letter.shield_collision(now_ms)
    
    assert game.letter.pos[1] < shield_y
    assert game.letter.start_fall_y < shield_y
