
import pytest
import asyncio
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test
from game.letter import GuessType

@async_test
async def test_rack_tile_consistency():
    """Verify that logical rack state matches visual rack display tiles."""
    game, mqtt, queue = await create_test_game(player_count=1)
    app = game._app
    
    # Initialize racks (factory might skip App.start which does this)
    app.rack_manager.initialize_racks_for_fair_play()
    # Trigger visual update (App.start usually does this)
    app._update_rack_display(0, 0, 0, None)
    await asyncio.sleep(0.1) # Allow events to process
    
    # 1. Initial State (should be empty depending on factory, but assuming empty for now or checking sync)
    # The factory might accept a falling letter or initialize empty.
    # Let's ensure it's empty or sync'd.
    logical_rack = app.rack_manager.get_rack(0)
    visual_rack = game.racks[0]
    

    
    assert logical_rack.letters() == visual_rack.letters()
    assert len(visual_rack.letters()) == 6
    
    # 2. Add letters
    # We can simulate accepting a letter via game.accept_letter or directly manipulating app/hardware events
    # simpler to use internal methods for integration test logic if possible,
    # but strictly we should use game.accept_letter(now_ms)

    # Freeze letter at position 0 for deterministic testing
    game.letter.freeze_at_position(0)
    game.letter.letter = "A"

    await game.accept_letter(0)
    await asyncio.sleep(0.1) # Allow events
    

    
    # We expect the letter at index 0 (or wherever letter_ix points) to be "A"
    # And string equality
    assert logical_rack.letters() == visual_rack.letters()
    assert logical_rack.letters()[0] == "A"
    
    # 3. Add expected behavior for test

    # 2. Add 'B' at same index 0 (should replace 'A')
    game.letter.freeze_at_position(0)  # Re-freeze for next letter placement
    game.letter.letter = "B"
    await game.accept_letter(0)
    await asyncio.sleep(0.1)
    
    # Expect replacement: AELNPS -> BELNPS

    assert logical_rack.letters() == visual_rack.letters()
    assert logical_rack.letters()[0] == "B"
    
    # 3. Simulate a guess
    # Since we lack full dictionary validation in this unit test scope, 
    # and add_guess doesn't inherently clear tiles without valid word logic,
    # we just verify consistency remains.
    
    app.add_guess("BELNPS", 0) # Guess the whole rack?
    await asyncio.sleep(0.1)
    
    # Verify consistency still holds (even if nothing happened)
    assert logical_rack.letters() == visual_rack.letters()
    
    # If we want to test removal, we'd need to mock Dictionary or trigger a "good guess" even manually
    # But checking consistency is enough for this test goal.

@async_test
async def test_rack_overflow_handling():
    """Verify that rack size remains constant (fixed slots)."""
    game, mqtt, queue = await create_test_game(player_count=1)
    app = game._app
    
    # Initialize implementation details
    app.rack_manager.initialize_racks_for_fair_play()
    app._update_rack_display(0, 0, 0, None)
    await asyncio.sleep(0.1)
    
    visual_rack = game.racks[0]
    assert len(visual_rack.letters()) == 6
    
    # Try to "fill" or modify many times
    letters = ["A", "B", "C", "D", "E", "F"]
    for i, char in enumerate(letters):
        # Target different indices
        game.letter.letter_ix = i % 6
        game.letter.letter = char
        await game.accept_letter(0)
        await asyncio.sleep(0.01)
        
    assert len(visual_rack.letters()) == 6
    
    # Attempt to add one more (should just replace something)
    game.letter.letter_ix = 0
    game.letter.letter = "G"
    await game.accept_letter(0)
    await asyncio.sleep(0.01)
    
    assert len(visual_rack.letters()) == 6
    # Should not crash
    assert game.running is True

@async_test
async def test_tile_movement_updates():
    """Verify that visual tile updates reflect state changes (e.g. pushback)."""
    game, mqtt, queue = await create_test_game(player_count=1, descent_mode="discrete")
    app = game._app
    
    # Initialize implementation details
    app.rack_manager.initialize_racks_for_fair_play()
    app._update_rack_display(0, 0, 0, None)
    await asyncio.sleep(0.1)
    
    # Add a letter so we have a tile to move
    # Freeze at position 1 for deterministic placement
    game.letter.freeze_at_position(1)
    game.letter.letter = "B"
    await game.accept_letter(0)
    await asyncio.sleep(0.1)
    
    logical_rack = game._app.rack_manager.get_rack(0)
    visual_rack = game.racks[0]

    # assert logical_rack.letters matches visual, and index 1 is B
    assert logical_rack.letters() == visual_rack.letters()
    assert logical_rack.letters()[1] == "B"
    
    # 3. Simulate a guess (which clears tiles)
    original_tiles = list(visual_rack.tiles)
    original_tile_obj = original_tiles[1] # Index 1 is B
    
    # We want to verify that an update triggers.
    # RackDisplay.update_rack replaces the list of tiles.
    # Let's trigger a logic that updates the rack.
    
    await game._app.load_rack(100)
    
    # Verify the tiles list might be new objects or same objects depending on implementation
    # But content should be same.
    assert visual_rack.letters() == logical_rack.letters()
    
    # If we manually mess with logical rack
    game._app.rack_manager.get_rack(0).replace_letter("Z", 1) # Replace B with Z at index 1
    # Note: remove_letters logic is different (removes by letter value, shifting?)
    # Rack doesn't have remove_letters? It has replace_letter.
    # Check Rack methods in tiles.py. 'remove_letters' not seen. 
    # 'guess' updates _last_guess but doesn't remove tiles?
    # Wait, Fair Play rule: rack ALWAYS has MAX_LETTERS. Replacing.
    # So we replace "B" with "Z".
    
    await game._app.load_rack(200)
    
    assert visual_rack.letters()[1] == "Z"
    
