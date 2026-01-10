import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.fixtures.game_factory import create_test_game, async_test
from hardware import cubes_to_game
from game.game_state import Game
from config import game_config
from types import SimpleNamespace

# =============================================================================
# Letter Lock Tests
# =============================================================================

@async_test
async def test_letter_lock_1_player_wiring(mock_hardware):
    """Verify 1-player mode wiring (sample check)."""
    game, _, _ = await create_test_game(descent_mode="discrete")
    game._app.player_count = 1
    p0_tiles = game._app._rack_manager.get_rack(0).get_tiles()
    
    # Check just one position to verify wiring works
    pos = 0
    expected_id = p0_tiles[pos].id
    await game._app.letter_lock(position=pos, locked=True, now_ms=1000)
    
    found = any(c.args[1] == 0 and c.args[2] == expected_id for c in mock_hardware.letter_lock.call_args_list)
    assert found, "Wiring check failed: Pos 0 should map to tile 0 on cube set 0"

@async_test
async def test_letter_lock_2_player_wiring(mock_hardware):
    """Verify 2-player mode wiring (sample check for both players)."""
    game, _, _ = await create_test_game(descent_mode="discrete")
    game._app.player_count = 2
    
    p0_tiles = game._app._rack_manager.get_rack(0).get_tiles()
    p1_tiles = game._app._rack_manager.get_rack(1).get_tiles()
    
    # Check P0 Wiring (Pos 0)
    await game._app.letter_lock(position=0, locked=True, now_ms=1000)
    p0_id = p0_tiles[0].id
    found_p0 = any(c.args[1] == 0 and c.args[2] == p0_id for c in mock_hardware.letter_lock.call_args_list)
    assert found_p0, "Wiring check failed: P0 Pos 0 should map to P0 tile"
    mock_hardware.letter_lock.reset_mock()
        
    # Check P1 Wiring (Pos 3 -> Rack Index 0)
    await game._app.letter_lock(position=3, locked=True, now_ms=1000)
    p1_id = p1_tiles[0].id
    found_p1 = any(c.args[1] == 1 and c.args[2] == p1_id for c in mock_hardware.letter_lock.call_args_list)
    assert found_p1, "Wiring check failed: P1 Pos 3 should map to P1 tile"

# =============================================================================
# Accept New Letter Tests
# =============================================================================

@async_test
async def test_accept_new_letter_2_player_mapping(mock_hardware):
    """Verify accept_new_letter correctly determines target player and offset in 2-player mode."""
    game, _, _ = await create_test_game(descent_mode="discrete")
    game._app.player_count = 2
    new_letter = "Z"
    
    # Test P1 Zone (Pos 3) -> Should affect P1 Rack Index 0
    p1_rack = game._app._rack_manager.get_rack(1)
    original_p1_tile_id = p1_rack.get_tiles()[0].id
    
    await game._app.accept_new_letter(new_letter, position=3, now_ms=2000)
    
    # Verify P1 rack changed
    new_p1_tiles = p1_rack.get_tiles()
    assert new_p1_tiles[0].letter == new_letter
    changed_tile_id = new_p1_tiles[0].id
    
    # Verify broadcast
    calls = mock_hardware.accept_new_letter.mock_calls
    # call args: (queue, letter, tile_id, cube_set_id, now)
    
    # Check P0 broadcast
    found_p0 = any(c.args[3] == 0 and c.args[2] == changed_tile_id for c in calls)
    assert found_p0, "Should broadcast change to Cube Set 0"
    
    # Check P1 broadcast
    found_p1 = any(c.args[3] == 1 and c.args[2] == changed_tile_id for c in calls)
    assert found_p1, "Should broadcast change to Cube Set 1"

# =============================================================================
# Load Rack Tests
# =============================================================================

@async_test
async def test_load_rack_skips_unstarted_players(mock_hardware):
    """Verify load_rack only talks to CubeSetManagers for started players."""
    game, _, _ = await create_test_game(descent_mode="discrete")
    game._app.player_count = 2
    
    # Case: Only P0 started
    mock_hardware.has_player_started_game.side_effect = lambda p: p == 0
    
    await game._app.load_rack(now_ms=3000)
    
    # Should call load_rack for P0 (cube set 0)
    # arg 3 is player/cube_set? Sig: load_rack(queue, tiles, cube_set_id, player, now)
    found_p0_cs = any(c.args[2] == 0 for c in mock_hardware.load_rack.mock_calls)
    assert found_p0_cs
    
    # Should NOT call for P1
    found_p1_cs = any(c.args[2] == 1 for c in mock_hardware.load_rack.mock_calls)
    assert not found_p1_cs

    mock_hardware.load_rack.reset_mock()

    # Case: Both started
    mock_hardware.has_player_started_game.side_effect = None # Reset
    mock_hardware.has_player_started_game.return_value = True
    
    await game._app.load_rack(now_ms=4000)
    found_p0 = any(c.args[2] == 0 for c in mock_hardware.load_rack.mock_calls)
    found_p1 = any(c.args[2] == 1 for c in mock_hardware.load_rack.mock_calls)
    assert found_p0 and found_p1

# =============================================================================
# Guess Tests
# =============================================================================

@async_test
async def test_guess_word_keyboard_player_mapping(mock_hardware):
    """Verify keyboard guesses use correct rack and cube set for player ID."""
    game, _, _ = await create_test_game(descent_mode="discrete")
    game._app.player_count = 2
    
    p1_rack = game._app._rack_manager.get_rack(1)
    target_ids = ["101", "102", "103"]
    
    with patch.object(p1_rack, 'letters_to_ids', return_value=target_ids) as mock_l2i:
             
        await game._app.guess_word_keyboard(guess="CAT", player=1, now_ms=5000)
        
        mock_l2i.assert_called_with("CAT")
        
        calls = mock_hardware.guess_tiles.mock_calls
        assert len(calls) == 1
        args = calls[0].args
        
        # args[1] = [[ids]]
        assert args[1] == [target_ids]
        # args[2] = cube_set_id (should be 1 for player 1)
        assert args[2] == 1
        # args[3] = player (1)
        assert args[3] == 1
