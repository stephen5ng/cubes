
import pytest
import os
import asyncio
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test, advance_seconds
from tests.fixtures.test_context import IntegrationTestContext
from core.dictionary import Dictionary
from game.letter import GuessType
# from hardware.cubes_to_game import state as cubes_state # Removed
from tests.fixtures.test_helpers import update_app_dictionary, drain_mqtt_queue
from tests.fixtures.dictionary_helpers import create_test_dictionary


# Helper to verify standard message publishing (points/shield)
async def verify_message_published(mqtt, queue, expected_topic_suffix):
    """Check if any published message topic ends with the given suffix."""
    # Process all queued messages
    await drain_mqtt_queue(mqtt, queue)
        
    found = False
    # Use real published messages list from FakeMqttClient
    for topic, message, retain in mqtt.published_messages:
        if topic.endswith(expected_topic_suffix):
            found = True
            break
    assert found, f"Expected MQTT message with topic suffix '{expected_topic_suffix}' not found in {[m[0] for m in mqtt.published_messages]}"

@async_test
async def test_good_guess_unique():
    """Test a valid, new word guess awards points and triggers a shield."""
    ctx = await IntegrationTestContext.create(players=[0])
    
    # Setup Dictionary
    from core.dictionary import Dictionary
    test_dict = Dictionary.from_words(["HELLO", "WORLD"], min_letters=3, max_letters=6)
    update_app_dictionary(ctx.game._app, test_dict)
    
    # 1. Setup Rack
    target_word = "HELLO"
    player = 0
    rack = ctx.game._app.rack_manager.get_rack(player)
    
    new_tiles = rack.get_tiles()
    for i, char in enumerate(target_word):
        new_tiles[i].letter = char
    rack.set_tiles(new_tiles)
    
    # 2. Make Guess
    tile_ids = [t.id for t in new_tiles[:len(target_word)]]
    
    result = await ctx.make_guess(tile_ids, player=player)

    # 3. Validation
    ctx.assert_shield_created("HELLO")
    ctx.assert_score_change(player, expected_delta=0) # Score 0 until animation? Wait, original test said score 0.
    # Actually, make_guess logic: `score_change = self.game.scores[player].score - initial_score`.
    # Original test said: `# Score remains 0 until animation completes`.
    # `Game.update_score` is called by `ScoreCard` which receives update from `Shield` collision?
    # No, App.guess_tiles -> _score_card.process_word -> returns score.
    # Does it update game.score immediately or create a shield with a score?
    # It creates a shield with score. Score component is updated when shield hits/flown away.
    # So assertions are consistent.

    ctx.assert_border_color("0x07E0")
    ctx.assert_flash_sent()


@async_test
async def test_old_guess():
    """Test that repeating a previously guessed word does not award points/shield."""
    game, mqtt, queue = await create_test_game()
    new_dict = create_test_dictionary(["HELLO"], min_letters=3, max_letters=6)
    update_app_dictionary(game._app, new_dict)
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    # Check initial state implicitly by App getter
    # assert game._app.get_player_border_color(0) is None



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
    # Verify yellow border for old guess (0xFFE0)
    assert game._app.get_player_border_color(0) == "0xFFE0"
    



@async_test
async def test_bad_guess_invalid_word():
    """Test that an invalid word (not in dictionary) is rejected."""
    ctx = await IntegrationTestContext.create(players=[0])
    
    # Setup Dictionary
    from core.dictionary import Dictionary
    # Dictionary only has "HELLO", but we guess "WORLD"
    test_dict = Dictionary.from_words(["HELLO"], min_letters=3, max_letters=6)
    update_app_dictionary(ctx.game._app, test_dict)
    
    player = 0
    
    # Setup Rack
    rack = ctx.game._app.rack_manager.get_rack(player)
    new_tiles = rack.get_tiles()
    target_word = "WORLD"
    for i, char in enumerate(target_word):
        new_tiles[i].letter = char
    rack.set_tiles(new_tiles)
    tile_ids = [t.id for t in new_tiles[:len(target_word)]]

    # Make Bad Guess
    result = await ctx.make_guess(tile_ids, player=player)
    
    # Assertions
    ctx.assert_score(player, 0)
    ctx.assert_border_color("0xFFFF") # White for bad guess


@async_test
async def test_bad_guess_missing_letters():
    """Test that guessing more letters than present in rack is rejected/filtered."""
    game, mqtt, queue = await create_test_game()
    new_dict = create_test_dictionary(["APPLE"], min_letters=3, max_letters=6)
    update_app_dictionary(game._app, new_dict)
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    # cubes_state.cube_set_managers[0].border_color = None


    
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
    # Verify white border for bad guess (0xFFFF)
    assert game._app.get_player_border_color(0) == "0xFFFF"
    assert game.scores[player].score == 0




@async_test
async def test_dictionary_length_constraints():
    """Test that words outside min/max length settings are ignored/invalid."""
    # Min 3, Max 6
    d = create_test_dictionary(["HI", "MEDIUM", "TOOLONGWORD"], min_letters=3, max_letters=6)
    
    assert not d.is_word("HI")
    assert d.is_word("MEDIUM")
    assert not d.is_word("TOOLONGWORD")

@async_test
async def test_dictionary_integration():
    """Test basic dictionary loading and lookup."""
    d = create_test_dictionary(["TEST", "WORD"], min_letters=3, max_letters=6)
    
    assert d.is_word("TEST")
    assert d.is_word("WORD")
    assert not d.is_word("FAKE")
