
import pytest
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test, advance_seconds, advance_frames
from game.letter import Letter
from config import game_config
import pygame

@async_test
async def test_letters_fall_at_constant_speed():
    """Test that letters fall vertically at a constant speed in timed mode."""
    # Create game with explicit short duration for TimeBasedDescentStrategy
    # 1 second duration implies descent rate = height / 1000.
    game, mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=1)
    
    # Initialize start_time_s which is usually set by game.start()
    game.start_time_s = 0
    game.running = True
    
    # Configure letter instance directly instead of patching
    game.letter.DROP_TIME_MS = 1000 # 1 second to drop
    game.letter.start(0)
    
    # Initial position should be at top (start_fall_y = 0)
    assert game.letter.start_fall_y == 0
    assert game.letter.pos[1] == 0

    # Advance 500ms (halfway)
    await advance_seconds(game, queue, 0.5)
    
    # In Timed Mode, the "red line" (start_fall_y) moves down continuously.
    expected_y_fraction = 0.5
    # Allow some margin for frame alignment
    current_y = game.letter.start_fall_y
    total_height = game.letter.height
    
    # We expect it to be roughly 50% down the playable area
    assert current_y > 0
    assert abs((current_y / total_height) - expected_y_fraction) < 0.1, f"Expected ~50% drop, got {current_y/total_height:.2f}"

    # Advance another 500ms (completion)
    await advance_seconds(game, queue, 0.55) 
    
    current_y = game.letter.start_fall_y
    # Should be at bottom
    assert current_y == total_height or abs((current_y / total_height) - 1.0) < 0.1, f"Expected ~100% drop, got {current_y/total_height:.2f}"


@async_test
async def test_letters_horizontal_oscillation():
    """Test that letters move horizontally back and forth."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    # Configure letter instance directly
    game.letter.NEXT_COLUMN_MS = 100
    game.letter.start(0)
    
    # Start at middle-ish? Actually start() resets letter_ix to 1. 
    start_ix = 1
    assert game.letter.letter_ix == start_ix
    
    # Advance 150ms -> should move +1 (to 2)
    await advance_seconds(game, queue, 0.15)
    
    assert game.letter.letter_ix == start_ix + 1, "Should have moved right by 1"
    
    # Manually force update to test boundary logic
    game.letter.letter_ix = 5
    game.letter.column_move_direction = 1
    game.letter.next_column_move_time_ms = 0 
    
    # Update once
    game.letter.update(pygame.Surface((1,1)), 1000) 
    
    # Should have bounced: 5 -> 6 -> bounce -> 4
    assert game.letter.letter_ix == 4
    assert game.letter.column_move_direction == -1
    
    game.letter.letter_ix = 0
    game.letter.column_move_direction = -1
    game.letter.next_column_move_time_ms = 0 
    
    # Update once
    game.letter.update(pygame.Surface((1,1)), 2000)
    
    # Should have bounced: 0 -> -1 -> bounce -> 1
    assert game.letter.letter_ix == 1
    assert game.letter.column_move_direction == 1


@async_test
async def test_letter_lock_on_behavior():
    """Test that letter stops moving horizontally when locked on (near bottom)."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    game.start_time_s = 0
    
    # Configure letter instance directly
    game.letter.NEXT_COLUMN_MS = 100
    game.letter.start(0)
    
    # Position letter near bottom
    # locked_on logic: (fraction >= 1) and (bottom + 2*inc > height)
    
    # Manually set vertical position
    game.letter.pos[1] = game.letter.height - game.letter.letter_height - 1
    
    # Pass time=100 so fraction (1 - remaining/100) becomes 1.0
    game.letter.draw(100)
    
    assert game.letter.locked_on, "Letter should be locked on when near bottom"
    
    # Now advance time past column move time
    initial_ix = game.letter.letter_ix
    
    # Time passes...
    await advance_seconds(game, queue, 1.0) 
    
    assert game.letter.letter_ix == initial_ix, "Letter should not move horizontally when locked on"


@async_test
async def test_letter_collision_with_rack_bottom():
    """Test behavior when letter hits the bottom (rack).
    
    In current implementation, falling to the bottom triggers proper 'acceptance'
    of the letter into the rack, not necessarily Game Over (unless rack full).
    """
    game, mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=2)
    game.start_time_s = 0
    
    # Ensure letter has content so acceptance logic works
    game.letter.letter = "A"
    
    # Configure letter instance directly
    game.letter.DROP_TIME_MS = 100
    game.letter.start(0)
    # Re-set letter because start() clears it
    game.letter.letter = "A"
    
    assert game.running
    # Check source of truth (RackManager)
    initial_tiles = game._app.rack_manager.get_rack(0).get_tiles()
    target_index = 1 # game.letter.start(0) resets index to 1
    initial_char = initial_tiles[target_index].letter
    
    # Ensure falling letter is different from existing tile
    new_letter = "X" if initial_char != "X" else "Y"
    game.letter.letter = new_letter
    
    # Let it drop all the way
    await advance_seconds(game, queue, 0.2) 
    
    # The game loop should have detected collision and accepted the letter.
    # Check that rack tile at index 1 was replaced
    current_tiles = game._app.rack_manager.get_rack(0).get_tiles()
    final_char = current_tiles[target_index].letter
    
    assert final_char == new_letter, f"Letter at index {target_index} should be {new_letter}, got {final_char}"
    
    # Check game is still running (valid collision)
    assert game.running, "Game should continue after valid letter acceptance"
