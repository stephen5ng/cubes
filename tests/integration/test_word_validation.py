
import pytest
import os
import asyncio
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test, advance_seconds
from core.dictionary import Dictionary
from game.letter import GuessType
from hardware.cubes_to_game import state as cubes_state


# Helper to verify standard message publishing (points/shield)
async def verify_message_published(mqtt, queue, expected_topic_suffix):
    """Check if any published message topic ends with the given suffix."""
    # Process all queued messages
    while not queue.empty():
        item = await queue.get()
        if isinstance(item, tuple):
             # (topic, payload, retain, qos/timestamp)
            topic, payload, retain, *_ = item
            await mqtt.publish(topic, payload, retain)
        else:
            await mqtt.publish(item.topic, item.payload)
        
    found = False
    # Use real published messages list from FakeMqttClient
    for topic, message, retain in mqtt.published_messages:
        if topic.endswith(expected_topic_suffix):
            found = True
            break
    assert found, f"Expected MQTT message with topic suffix '{expected_topic_suffix}' not found in {[m[0] for m in mqtt.published_messages]}"
    
def update_app_dictionary(app, new_dictionary):
    """Helper to update dictionary references across App components."""
    app._dictionary = new_dictionary
    app._score_card.dictionary = new_dictionary
    app.rack_manager.dictionary = new_dictionary

@async_test
async def test_good_guess_unique():
    """Test a valid, new word guess awards points and triggers a shield."""
    custom_dict_path = "/tmp/test_good_guess.txt"
    with open(custom_dict_path, "w") as f:
        f.write("HELLO\nWORLD\n")
    
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(min_letters=3, max_letters=6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)

    game.start_time_s = 0
    # Force mapping for test environment
    game._app._player_to_cube_set = {0: 0}

    
    # 1. Setup Rack
    target_word = "HELLO"
    player = 0
    rack = game._app.rack_manager.get_rack(player)
    
    new_tiles = rack.get_tiles()
    for i, char in enumerate(target_word):
        new_tiles[i].letter = char
    rack.set_tiles(new_tiles)
    
    # 2. Make Guess
    tile_ids = [t.id for t in new_tiles[:len(target_word)]]
    await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=1000)
    await asyncio.sleep(0) # Let the async task scheduled by guess_tiles complete

    
    
    # 3. Validation
    # Visual score only updates after shield collision animation.
    # Check Shield existence implies success.
    assert len(game.shields) == 1
    assert game.shields[0].letters == "HELLO"
    assert game.shields[0].active
    # Score remains 0 until animation completes
    assert game.scores[player].score == 0
    
    await verify_message_published(mqtt, queue, "/flash")
    # Verify green border (0x07E0) - good guess
    assert cubes_state.cube_set_managers[0].border_color == "0x07E0"
    
    os.remove(custom_dict_path)


@async_test
async def test_old_guess():
    """Test that repeating a previously guessed word does not award points/shield."""
    custom_dict_path = "/tmp/test_old_guess.txt"
    with open(custom_dict_path, "w") as f:
        f.write("HELLO\n")
    
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(3, 6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    cubes_state.cube_set_managers[0].border_color = None



    target_word = "HELLO"
    player = 0
    rack = game._app.rack_manager.get_rack(player)
    
    new_tiles = rack.get_tiles()
    for i, char in enumerate(target_word):
        new_tiles[i].letter = char
    rack.set_tiles(new_tiles)
    tile_ids = [t.id for t in new_tiles[:len(target_word)]]
    
    # 1. First Guess (Good)
    await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=1000)
    await asyncio.sleep(0)
    # First guess creates shield
    assert len(game.shields) == 1
    mqtt.clear_published()
    
    # 2. Second Guess (Old)
    await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=2000)
    await asyncio.sleep(0)
    
    # Should NOT create a new shield
    assert len(game.shields) == 1
    
    # Should NOT create a new shield
    assert len(game.shields) == 1
    
    # Verify yellow border for old guess (0xFFE0)
    assert cubes_state.cube_set_managers[0].border_color == "0xFFE0"
    
    os.remove(custom_dict_path)


@async_test
async def test_bad_guess_invalid_word():
    """Test that an invalid word (not in dictionary) is rejected."""
    custom_dict_path = "/tmp/test_bad_guess.txt"
    with open(custom_dict_path, "w") as f:
        f.write("HELLO\n") 
        
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(3, 6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    
    player = 0
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    cubes_state.cube_set_managers[0].border_color = None


    rack = game._app.rack_manager.get_rack(player)
    
    new_tiles = rack.get_tiles()
    target_word = "WORLD"
    for i, char in enumerate(target_word):
        new_tiles[i].letter = char
    rack.set_tiles(new_tiles)
    tile_ids = [t.id for t in new_tiles[:len(target_word)]]

    # Make Bad Guess
    await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=1000)
    await asyncio.sleep(0.1) # Need more time for async processing?

    await asyncio.sleep(0)
    
    assert game.scores[player].score == 0
    # Verify white border for bad guess (0xFFFF)
    assert cubes_state.cube_set_managers[0].border_color == "0xFFFF"
    
    os.remove(custom_dict_path)


@async_test
async def test_bad_guess_missing_letters():
    """Test that guessing more letters than present in rack is rejected/filtered."""
    custom_dict_path = "/tmp/test_missing.txt"
    with open(custom_dict_path, "w") as f:
        f.write("APPLE\n")
        
    game, mqtt, queue = await create_test_game()
    game._app._dictionary = Dictionary(3, 6)
    game._app._dictionary.read(custom_dict_path, custom_dict_path)
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    cubes_state.cube_set_managers[0].border_color = None


    
    player = 0
    rack = game._app.rack_manager.get_rack(player)
    
    tiles = rack.get_tiles()
    tiles[0].letter = 'A'
    for t in tiles[1:]:
        t.letter = 'Z'
    rack.set_tiles(tiles)
    
    # Guess APPLE. Only 'A' is found. 'A' is < min length (3). 
    # Should trigger bad_guess (or simply be ignored/invalid).
    # Since dictionary check happens on the IDs provided, and only 1 ID is provided...
    # Dictionary lookup for "A" fails.
    
    await game._app.guess_word_keyboard("APPLE", player, 1000)
    await asyncio.sleep(0)
    
    await game._app.guess_word_keyboard("APPLE", player, 1000)
    await asyncio.sleep(0)
    
    # Verify white border for bad guess (0xFFFF)
    assert cubes_state.cube_set_managers[0].border_color == "0xFFFF"
    assert game.scores[player].score == 0

    os.remove(custom_dict_path)


@async_test
async def test_dictionary_length_constraints():
    """Test that words outside min/max length settings are ignored/invalid."""
    custom_dict_path = "/tmp/test_constraints.txt"
    with open(custom_dict_path, "w") as f:
        f.write("HI\nMEDIUM\nTOOLONGWORD\n")
        
    # Min 3, Max 6
    d = Dictionary(min_letters=3, max_letters=6)
    d.read(custom_dict_path, custom_dict_path)
    
    assert not d.is_word("HI")
    assert d.is_word("MEDIUM")
    assert not d.is_word("TOOLONGWORD")
    
    os.remove(custom_dict_path)

@async_test
async def test_dictionary_integration():
    """Test basic dictionary loading and lookup."""
    custom_dict_path = "/tmp/test_dict.txt"
    with open(custom_dict_path, "w") as f:
        f.write("TEST\nWORD\n")
        
    d = Dictionary(3, 6)
    d.read(custom_dict_path, custom_dict_path)
    
    assert d.is_word("TEST")
    assert d.is_word("WORD")
    assert not d.is_word("FAKE")
    
    os.remove(custom_dict_path)
