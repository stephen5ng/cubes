
import pytest
import asyncio
import pygame
from tests.fixtures.game_factory import create_test_game, async_test
from game.descent_strategy import DiscreteDescentStrategy, TimeBasedDescentStrategy

@async_test
async def test_discrete_mode_descent_behavior():
    """Verify that in discrete mode, the red line only moves down when expected events occur."""
    # Create game in DISCRETE mode (default)
    # The factory defaults to discrete if not specified or if we pass specific config?
    # Factory uses game_config.TIMED_DURATION_S to create Game, but Game defaults to "discrete".
    # We need to verify what create_test_game does. 
    # It calls Game(...) without descent_mode initially? 
    # Let's check factory... it passes `descent_mode` if provided?
    # Actually create_test_game helper args: `def create_test_game(player_count=1, ...)`
    # It seems to just create App then Game. 
    # App creates Game in `start()`. `App.start` creates `Game`.
    # `App.start` reads `self.config.descen_mode` ??
    # I need to ensure I can control mode via config injection or factory.
    
    # Assuming factory creates 'discrete' by default (as App/Game default to discrete).
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # 1. Initial State
    initial_y = game.letter.start_fall_y
    assert isinstance(game.letter.descent_strategy, DiscreteDescentStrategy)
    
    # 2. Advance time (no events)
    await asyncio.sleep(0.5)
    
    # 3. Verify NO descent of red line
    # The LETTER might fall (current position), but the RED LINE (start_fall_y) 
    # should be stable in discrete mode until an event.
    assert game.letter.start_fall_y == initial_y
    
    # 4. Trigger event (e.g. word completion mock)
    # The descent strategy in discrete mode triggers on 'new_fall'.
    # `game.accept_letter` calls `new_fall`.
    game.letter.new_fall(0) # triggering descent manually to verify strategy behavior
    
    # 5. Verify descent
    assert game.letter.start_fall_y > initial_y


@async_test
async def test_timed_mode_continuous_descent():
    """Verify that in timed mode, the red line moves down continuously."""
    # Create game in TIMED mode directly via factory
    game, mqtt, queue = await create_test_game(player_count=1, descent_mode="timed")
    
    # 1. Initial State
    initial_y = game.letter.start_fall_y
    assert isinstance(game.letter.descent_strategy, TimeBasedDescentStrategy)
    
    # 2. Advance time
    # TimeBasedDescentStrategy updates based on elapsed time from start_time_ms.
    # The game starts at t=0 (mock time).
    # Update letter with new time (e.g. 5 seconds later)
    # Note: mocking time might be needed if update() calls get_ticks internally, 
    # but Letter.update takes now_ms as arg.
    
    game.letter.update(pygame.Surface((1,1)), 5000) 
    
    # 3. Verify descent
    assert game.letter.start_fall_y > initial_y

@async_test
async def test_timed_mode_yellow_line_presence():
    """Verify that yellow line exists in timed mode."""
    game, mqtt, queue = await create_test_game(player_count=1, descent_mode="timed")
    
    assert game.yellow_source is not None
    assert isinstance(game.yellow_tracker.descent_strategy, TimeBasedDescentStrategy)

@async_test
async def test_discrete_mode_no_yellow_line():
    """Verify that yellow line is NOT active in discrete mode."""
    game, mqtt, queue = await create_test_game(player_count=1)
    # Default is discrete.
    
    # Assertion: Yellow source should be None (to be implemented)
    assert game.yellow_source is None
