
import logging
import pytest
from unittest.mock import patch, AsyncMock

from tests.fixtures.game_factory import create_test_game, async_test, wait_for_guess_processing
from tests.fixtures.mqtt_helpers import simulate_word_formation
from config import game_config
from core.tiles import Tile
import asyncio

logger = logging.getLogger(__name__)

def create_tiles_for_word(word: str) -> list[Tile]:
    """Helper to create a list of Tile objects from a word string."""
    return [Tile(letter, str(i)) for i, letter in enumerate(word)]

def create_ids_for_word(word: str) -> list[str]:
    """Helper to create list of IDs for a word (matching create_tiles_for_word)."""
    return [str(i) for i in range(len(word))]

@async_test
async def test_long_word_formation():
    """Verify forming a word with 7 letters (requires patching MAX_LETTERS)."""
    # Patch MAX_LETTERS to 7 for this test
    with patch('config.game_config.MAX_LETTERS', 7):
        game, mqtt, queue = await create_test_game()

        # Manually ensure dictionary allows 7 letters
        game._app._dictionary._max_letters = 7
        game._app._dictionary._all_words.add("TESTING")
        
        rack = game._app.rack_manager.get_rack(0)
        rack._max_size = 7
        rack.set_tiles(create_tiles_for_word("TESTING"))
        
        await start_player_turn(game, mqtt, player=0)
        
        # Mock hardware.good_guess on the injected interface
        # We need to target the specific instance method on the hardware object attached to the app
        with patch.object(game._app.hardware, 'good_guess', new_callable=AsyncMock) as mock_good_guess:
            # Trigger guess via APP logic
            await game._app.guess_tiles(create_ids_for_word("TESTING"), False, 0, 1000)
        
        # Expected score: 7 (length) + 10 (Bingo if 7 == MAX_LETTERS) = 17
        await wait_for_guess_processing(game, queue, player=0, expected_score=17, expected_word="TESTING")
        
        assert game.scores[0].score == 17
        assert "TESTING" in game.guesses_manager.guess_to_player

@async_test
async def test_rapid_guess_sequence():
    """Test multiple guesses in rapid succession."""
    game, mqtt, queue = await create_test_game()
    await start_player_turn(game, mqtt, player=0)
    
    words = ["CAT", "DOG", "BAT"]
    game._app._dictionary._all_words.update(words)
    
    rack = game._app.rack_manager.get_rack(0)
    
    total_score = 0
    
    for i, word in enumerate(words):
        # cheat: put letters in rack
        rack.set_tiles(create_tiles_for_word(word))
        
        await game._app.guess_tiles(create_ids_for_word(word), False, 0, 1000 + i*100)
        
        total_score += len(word)
        if len(word) == game_config.MAX_LETTERS:
            total_score += 10 # Bonus
            
        await wait_for_guess_processing(game, queue, 0, total_score, word)

    assert game.scores[0].score == total_score
    for word in words:
        assert word in game.guesses_manager.guess_to_player

@async_test
async def test_rack_exhaustion():
    """Verify behavior when a player uses all tiles in their rack."""
    game, mqtt, queue = await create_test_game()
    await start_player_turn(game, mqtt, player=0)
    
    target_word = "ABACUS" # 6 letters
    game._app._dictionary._all_words.add(target_word)
    
    rack = game._app.rack_manager.get_rack(0)
    rack.set_tiles(create_tiles_for_word(target_word)) 
    original_tiles = list(rack.get_tiles()) 
    
    # Use move_tiles=True to simulate tile consumption
    await game._app.guess_tiles(create_ids_for_word(target_word), True, 0, 1000)
    
    expected_score = len(target_word) + 10 # Bingo bonus (6 == MAX)
    await wait_for_guess_processing(game, queue, 0, expected_score, target_word)
    
    # Verify rack logic: Tiles are NOT replaced in this game, but rearranged/highlighted
    # Just verify score and that "exhaustion" (full rack word) counts as Bingo
    assert game.scores[0].score == expected_score
    
    # Verify we can still form words (rack not empty/broken)
    assert len(rack.get_tiles()) == game_config.MAX_LETTERS

@async_test
async def test_bingo_scoring():
    """Verify that max-length words trigger the Bingo bonus."""
    game, mqtt, queue = await create_test_game()
    await start_player_turn(game, mqtt, player=0)
    
    word = "ABCDEF"
    game._app._dictionary._all_words.add(word)
    
    rack = game._app.rack_manager.get_rack(0)
    rack.set_tiles(create_tiles_for_word(word))
    
    await game._app.guess_tiles(create_ids_for_word(word), False, 0, 1000)
    
    # Score = 6 + 10 = 16
    await wait_for_guess_processing(game, queue, 0, 16, word)
    assert game.scores[0].score == 16

async def start_player_turn(game, mqtt, player=0):
    """Helper to simulate player start."""
    # Check if rack has tiles, if not, force a reload or start
    if not game._app.rack_manager.get_rack(player).get_tiles():
         # Simulate start
         await game._app.start(0)
