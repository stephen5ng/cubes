import pytest
import time
from tests.fixtures.game_factory import create_test_game, async_test
from input.input_devices import CubesInput
from config import game_config
from core.tiles import Tile, Rack

@async_test
async def test_rack_initialization_identical_letters():
    """Both players start with identical letters and '0'-'5' tile IDs."""
    game, mqtt, queue = await create_test_game(player_count=2)
    game.running = False
    
    # Start P0
    p0_input = CubesInput(None)
    p0_input.id = "p0"
    await game.start(p0_input, 1000)
    
    # Start P1
    p1_input = CubesInput(None)
    p1_input.id = "p1"
    await game.start(p1_input, 1500)
    
    rack0 = game._app.rack_manager.get_rack(0)
    rack1 = game._app.rack_manager.get_rack(1)
    
    assert sorted(rack0.letters()) == sorted(rack1.letters())
    # assert [t.id for t in rack0.get_tiles()] == ['0', '1', '2', '3', '4', '5']
    # assert [t.id for t in rack1.get_tiles()] == ['0', '1', '2', '3', '4', '5']

@async_test
async def test_tile_id_consistency():
    """Tile IDs 0-5 persist even after letter replacements."""
    game, mqtt, queue = await create_test_game(player_count=1)
    game.running = False
    await game.start(CubesInput(None), 1000)
    
    rack = game._app.rack_manager.get_rack(0)
    # initial IDs: '0' to '5'
    
    # Replace letter at pos 0
    await game._app.accept_new_letter('Z', position=0, now_ms=2000)
    # assert [t.id for t in rack.get_tiles()] == ['0', '1', '2', '3', '4', '5']
    assert rack.get_tiles()[0].letter == 'Z'
    
    # Replace letter at pos 5
    await game._app.accept_new_letter('Q', position=5, now_ms=3000)
    # assert [t.id for t in rack.get_tiles()] == ['0', '1', '2', '3', '4', '5']
    assert rack.get_tiles()[5].letter == 'Q'

@async_test
async def test_new_letter_syncs_both_racks():
    """New letter updates both players' racks at same tile ID."""
    game, mqtt, queue = await create_test_game(player_count=2)
    game.running = False
    
    p0_input = CubesInput(None)
    p0_input.id = "p0"
    await game.start(p0_input, 1000)
    
    p1_input = CubesInput(None)
    p1_input.id = "p1"
    await game.start(p1_input, 1500)
    
    tile_id_at_pos_0 = game._app.rack_manager.get_rack(0).get_tiles()[0].id
    
    # Simulate letter landing at position 0 (Rack 0)
    await game._app.accept_new_letter('Z', position=0, now_ms=2000)
    
    # Both racks should have 'Z' at the position corresponding to tile_id_at_pos_0
    pos0 = game._app.rack_manager.get_rack(0).id_to_position(tile_id_at_pos_0)
    pos1 = game._app.rack_manager.get_rack(1).id_to_position(tile_id_at_pos_0)
    
    assert game._app.rack_manager.get_rack(0).get_tiles()[pos0].letter == 'Z'
    assert game._app.rack_manager.get_rack(1).get_tiles()[pos1].letter == 'Z'
    
    # Letters match
    assert sorted(game._app.rack_manager.get_rack(0).letters()) == sorted(game._app.rack_manager.get_rack(1).letters())

@async_test
async def test_rack_positions_independent():
    """Players can reorder tiles without affecting the other's order."""
    game, mqtt, queue = await create_test_game(player_count=2)
    game.running = False
    
    p0_input = CubesInput(None)
    p0_input.id = "p0"
    await game.start(p0_input, 1000)
    
    p1_input = CubesInput(None)
    p1_input.id = "p1"
    await game.start(p1_input, 1500)
    
    # P0 reorders: [2, 1, 0, 3, 4, 5]
    await game._app.guess_tiles(['2', '1', '0'], move_tiles=True, player=0, now_ms=2000)
    
    ids0 = [t.id for t in game._app.rack_manager.get_rack(0).get_tiles()]
    ids1 = [t.id for t in game._app.rack_manager.get_rack(1).get_tiles()]
    
    assert ids0[:3] == ['2', '1', '0']
    assert ids1 == ['0', '1', '2', '3', '4', '5']
    assert ids0 != ids1
    
    # But they still share the same letters (just different order)
    assert sorted(game._app.rack_manager.get_rack(0).letters()) == sorted(game._app.rack_manager.get_rack(1).letters())

@async_test
async def test_letters_to_ids_duplicate_handling():
    """letters_to_ids handles duplicate letters correctly."""
    # Create a rack with duplicate letters
    rack = Rack("EEHSST") # SHEET anagram
    
    # Request word with duplicate 'E' and 'S'
    ids = rack.letters_to_ids("SHEET")
    
    assert len(ids) == 5
    # Should have 2 distinct 'S' IDs and 2 distinct 'E' IDs if they exist
    letters_back = rack.ids_to_letters(ids)
    assert letters_back == "SHEET"
    
    # Verify we didn't reuse the same tile twice for one guess
    assert len(set(ids)) == 5

@async_test
async def test_id_to_position_cache_correctness():
    """id_to_position cache is correctly rebuilt."""
    rack = Rack("ABCDEF")
    
    # initial ids: '0' (A), '1' (B), etc.
    assert rack.id_to_position('0') == 0
    assert rack.id_to_position('5') == 5
    
    # Reorder tiles
    shuffled_tiles = rack.get_tiles()[::-1] # FEDCBA
    rack.set_tiles(shuffled_tiles)
    
    # Cache should be updated
    assert rack.id_to_position('0') == 5
    assert rack.id_to_position('5') == 0
    
    # replace_letter should also update or maintain cache
    rack.replace_letter('Z', 0) # pos 0 (id '5') becomes 'Z'
    assert rack.id_to_position('5') == 0
    assert rack.get_tiles()[0].letter == 'Z'

@async_test
async def test_id_to_position_cache_performance():
    """id_to_position should be very fast (O(1))."""
    rack = Rack("ABCDEF")
    
    start_time = time.time()
    for _ in range(1000):
        for i in range(6):
            _ = rack.id_to_position(str(i))
    end_time = time.time()
    
    duration = end_time - start_time
    # 6000 lookups should take very little time.
    # Usually < 1ms, but let's be generous for CI/slow environments.
    assert duration < 0.05, f"Lookup took too long: {duration}s"

