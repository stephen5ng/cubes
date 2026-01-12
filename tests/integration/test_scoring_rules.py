
import pytest
import asyncio
from unittest.mock import MagicMock
from tests.fixtures.game_factory import create_test_game, async_test
from core.dictionary import Dictionary
from hardware.cubes_to_game import state as cubes_state
from config import game_config
from tests.fixtures.test_helpers import update_app_dictionary

@async_test
async def test_word_score_matches_length():
    """Verify that words of length 3-5 award points equal to their length."""
    custom_dict_path = "/tmp/test_scoring_length.txt"
    with open(custom_dict_path, "w") as f:
        f.write("CAT\nFOUR\nFIVES\n")
        
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(min_letters=3, max_letters=6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    
    # Force mapping
    game._app._player_to_cube_set = {0: 0}
    player = 0
    rack = game._app.rack_manager.get_rack(player)

    # 1. Helper to setup rack and guess
    async def guess_word(word):
        tiles = rack.get_tiles()
        for i, char in enumerate(word):
            tiles[i].letter = char
        rack.set_tiles(tiles)
        tile_ids = [t.id for t in tiles[:len(word)]]
        await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=1000)
        await asyncio.sleep(0)
    
    # Test 3 letters
    await guess_word("CAT")
    assert getattr(game.shields[-1], 'score') == 3
    
    # Test 4 letters
    await guess_word("FOUR")
    assert getattr(game.shields[-1], 'score') == 4
    
    # Test 5 letters
    await guess_word("FIVES")
    assert getattr(game.shields[-1], 'score') == 5

    # Cleanup
    import os
    os.remove(custom_dict_path)

@async_test
async def test_bingo_bonus():
    """Verify that a word using MAX_LETTERS awards an additional 10 points."""
    custom_dict_path = "/tmp/test_scoring_bingo.txt"
    with open(custom_dict_path, "w") as f:
        f.write("SIXLET\n")
        
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(min_letters=3, max_letters=6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    game._app._player_to_cube_set = {0: 0}
    player = 0
    rack = game._app.rack_manager.get_rack(player)
    
    # Max letters is 6 by default
    assert game_config.MAX_LETTERS == 6
    
    # Setup rack
    word = "SIXLET"
    tiles = rack.get_tiles()
    for i, char in enumerate(word):
        tiles[i].letter = char
    rack.set_tiles(tiles)
    tile_ids = [t.id for t in tiles[:len(word)]]
    
    # Guess
    await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=1000)
    await asyncio.sleep(0)
    
    # Expect 6 (length) + 10 (bonus) = 16
    assert game.shields[-1].score == 16
    
    import os
    os.remove(custom_dict_path)

@async_test
async def test_bingo_only_for_full_rack():
    """Verify bonus logic adheres strictly to MAX_LETTERS check."""
    # Note: ScoreCard checks `if len(word) == game_config.MAX_LETTERS`.
    # So if we somehow guessed a 5 letter word, even if rack was 5 size (hypothetically), it wouldn't Bingo unless MAX_LETTERS changed.
    pass # Covered implicitly by test_word_score_matches_length("FIVES") -> 5 points (not 15).


@async_test
async def test_cumulative_scoring():
    """Verify that scores accumulate correctly across multiple words."""
    custom_dict_path = "/tmp/test_scoring_cumulative.txt"
    with open(custom_dict_path, "w") as f:
        f.write("ONE\nTWO\n")
        
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(3, 6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    game._app._player_to_cube_set = {0: 0}
    player = 0
    rack = game._app.rack_manager.get_rack(player)
    
    score_component = game.scores[player]
    assert score_component.score == 0
    
    # Helper
    async def make_guess(word, now_ms):
        tiles = rack.get_tiles()
        # Set specific letters to ensuring we have them
        for i, char in enumerate(word):
            tiles[i].letter = char
        rack.set_tiles(tiles)
        tile_ids = [t.id for t in tiles[:len(word)]]
        await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=now_ms)
        await asyncio.sleep(0)

    # 1. Guess "ONE" (3 points)
    await make_guess("ONE", 1000)
    
    shield1 = game.shields[0]
    assert shield1.score == 3
    
    # Simulate collision
    score_component.update_score(shield1.score)
    assert score_component.score == 3
    
    # 2. Guess "TWO" (3 points)
    await make_guess("TWO", 2000)
    
    shield2 = game.shields[1]
    assert shield2.score == 3
    
    # Simulate collision
    score_component.update_score(shield2.score)
    assert score_component.score == 6
    
    import os
    os.remove(custom_dict_path)

@async_test
async def test_failed_guesses_no_score():
    """Verify that old/bad guesses do not affect the score."""
    custom_dict_path = "/tmp/test_scoring_failed.txt"
    with open(custom_dict_path, "w") as f:
        f.write("GOOD\n")
        
    game, mqtt, queue = await create_test_game()
    new_dict = Dictionary(3, 6)
    new_dict.read(custom_dict_path, custom_dict_path)
    update_app_dictionary(game._app, new_dict)
    game._app._player_to_cube_set = {0: 0}
    player = 0
    rack = game._app.rack_manager.get_rack(player)

    async def make_guess(word, now_ms):
        tiles = rack.get_tiles()
        # Ensure tiles exist for the word (if 'move_tiles' was true we'd need to be careful, but here false)
        # But we need to set letters on tiles to match the word for the ID lookup to work logically? 
        # Actually App.guess_tiles takes IDs. Rack maps IDs to letters. 
        # So we MUST ensure rack has those letters for those IDs.
        for i, char in enumerate(word):
            tiles[i].letter = char
        rack.set_tiles(tiles)
        tile_ids = [t.id for t in tiles[:len(word)]]
        await game._app.guess_tiles(tile_ids, move_tiles=False, player=player, now_ms=now_ms)
        await asyncio.sleep(0)
    
    # 1. Good guess
    await make_guess("GOOD", 1000)
    assert len(game.shields) == 1
    assert game.shields[0].score == 4
    
    # 2. Old guess
    original_shield_count = len(game.shields)
    await make_guess("GOOD", 2000)
    # Should be no new shield
    assert len(game.shields) == original_shield_count
    
    # 3. Bad guess
    # For bad guess, we set the letters to BADX
    await make_guess("BADX", 3000)
    assert len(game.shields) == original_shield_count
    
    import os
    os.remove(custom_dict_path)


@async_test
async def test_score_persistence():
    """Verify score is maintained during updates."""
    # Since Score is just a python object holding an int, this is trivial, 
    # but ensuring it doesn't reset unexpectedly is good.
    game, mqtt, queue = await create_test_game()
    score_component = game.scores[0]
    score_component.score = 100
    
    # Simulate a rack update or other event
    await game.update_rack([], 0, 0, 0, 1000)
    
    assert score_component.score == 100

