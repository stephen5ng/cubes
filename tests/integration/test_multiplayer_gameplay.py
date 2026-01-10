"""Multiplayer Integration Tests

Tests core gameplay mechanics for 2-player mode:
- Competitive scoring
- Independent tracking
- Rack isolation (via App)
"""
import pytest
from tests.fixtures.game_factory import create_test_game, async_test, wait_for_guess_processing, run_until_condition

@async_test
async def test_two_player_competitive():
    """Verify two players can score competitively."""
    game, _mqtt, queue = await create_test_game(player_count=2)
    
    # P0 scores
    await game.stage_guess(3, "CAT", 0, 1000)
    # Wait for P0 score
    await wait_for_guess_processing(game, queue, player=0, expected_score=3, expected_word="CAT")
    
    assert game.scores[0].score == 3
    assert game.scores[1].score == 0
    
    # P1 scores
    await game.stage_guess(4, "DOGS", 1, 2000)
    # Wait for P1 score
    await wait_for_guess_processing(game, queue, player=1, expected_score=4, expected_word="DOGS")
    
    assert game.scores[0].score == 3
    assert game.scores[1].score == 4
    
    # Verify guesses maintained
    assert game.guesses_manager.guess_to_player["CAT"] == 0
    assert game.guesses_manager.guess_to_player["DOGS"] == 1

@async_test
async def test_two_player_scoring_independent():
    """Verify scores are tracked independently (no cross-talk)."""
    game, _mqtt, queue = await create_test_game(player_count=2)
    
    # P0 scores big
    await game.stage_guess(10, "BINGO", 0, 1000)
    await run_until_condition(game, queue, lambda: game.scores[0].score == 10)
    
    assert game.scores[1].score == 0
    
    # P1 scores small
    await game.stage_guess(2, "HI", 1, 2000)
    await run_until_condition(game, queue, lambda: game.scores[1].score == 2)
    
    assert game.scores[0].score == 10
    assert game.scores[1].score == 2


@async_test
async def test_two_player_rack_isolation():
    """Verify racks start shared but diverge after moves."""
    game, _mqtt, queue = await create_test_game(player_count=2)
    
    rack0 = game._app.rack_manager.get_rack(0).get_tiles()
    rack1 = game._app.rack_manager.get_rack(1).get_tiles()
    
    # 1. Start synchronized (Shared Start)
    ids0 = [t.id for t in rack0]
    ids1 = [t.id for t in rack1]
    assert ids0 == ids1
    
    # 2. Diverge after a guess
    # Simulate P0 guess causing tile refresh
    # Use tiles from the middle to force reordering (moves guessed tiles to front)
    guess_ids = ids0[3:6]
    await game._app.guess_tiles(guess_ids, True, 0, 1000)
    
    new_rack0 = game._app.rack_manager.get_rack(0).get_tiles()
    new_rack1 = game._app.rack_manager.get_rack(1).get_tiles()
    
    # Racks should now be different objects (App creates new list for P0)
    # And contents should likely differ (order or new tiles)
    new_ids0 = [t.id for t in new_rack0]
    new_ids1 = [t.id for t in new_rack1]
    
    assert new_ids0 != new_ids1
