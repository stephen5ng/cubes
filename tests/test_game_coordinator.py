"""Test GameCoordinator parameter management for MQTT game/start."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock
from game.game_coordinator import GameCoordinator
from config.game_params import GameParams
from game.components import StarsDisplay, NullStarsDisplay


@pytest.mark.asyncio
async def test_set_pending_game_params():
    """Verify that pending game params are stored correctly."""
    coordinator = GameCoordinator()
    params = GameParams(
        descent_mode="timed",
        descent_duration_s=180,
        one_round=True,
        min_win_score=90,
        stars=True,
        level=1
    )

    coordinator.set_pending_game_params(params)

    assert coordinator.pending_game_params == params


@pytest.mark.asyncio
async def test_apply_pending_params_updates_game():
    """Verify that apply_pending_params updates game attributes."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()
    coordinator.game.rack_metrics = MagicMock()

    # Set up mock game
    coordinator.game.one_round = False
    coordinator.game.min_win_score = 0
    coordinator.game.level = 0
    coordinator.game.descent_duration_s = 120
    coordinator.game.stars_display = NullStarsDisplay()
    coordinator.game.sound_manager = MagicMock()
    coordinator.game.scores = [MagicMock(), MagicMock()]

    # Set pending params
    params = GameParams(
        descent_mode="timed",
        descent_duration_s=180,
        one_round=True,
        min_win_score=90,
        stars=False,
        level=2
    )
    coordinator.set_pending_game_params(params)

    # Apply params
    needs_re_setup = await coordinator.apply_pending_params()

    # Verify game was updated
    assert coordinator.game.one_round is True
    assert coordinator.game.min_win_score == 90
    assert coordinator.game.level == 2
    assert coordinator.game.descent_duration_s == 180
    assert coordinator.pending_game_params is None  # Should be cleared

    # Should return True because descent_mode/duration changed
    assert needs_re_setup is True


@pytest.mark.asyncio
async def test_apply_pending_params_enables_stars():
    """Verify that apply_pending_params can enable stars display."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()
    coordinator.game.rack_metrics = MagicMock()
    coordinator.game.sound_manager = MagicMock()

    # Set up mock game without stars
    coordinator.game.one_round = False
    coordinator.game.min_win_score = 0
    coordinator.game.level = 0
    coordinator.game.descent_duration_s = 120
    coordinator.game.stars_display = NullStarsDisplay()
    coordinator.game.scores = [MagicMock(stars_enabled=False), MagicMock(stars_enabled=False)]

    # Set pending params with stars enabled
    params = GameParams(
        descent_mode="discrete",
        descent_duration_s=120,
        one_round=False,
        min_win_score=90,
        stars=True,
        level=0
    )
    coordinator.set_pending_game_params(params)

    # Apply params
    await coordinator.apply_pending_params()

    # Verify stars display was replaced
    assert isinstance(coordinator.game.stars_display, StarsDisplay)
    assert coordinator.game.stars_display.min_win_score == 90
    # Verify scores were updated
    assert coordinator.game.scores[0].stars_enabled is True
    assert coordinator.game.scores[1].stars_enabled is True


@pytest.mark.asyncio
async def test_apply_pending_params_disables_stars():
    """Verify that apply_pending_params can disable stars display."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()
    coordinator.game.rack_metrics = MagicMock()
    coordinator.game.sound_manager = MagicMock()

    # Set up mock game with stars already enabled
    mock_stars_display = MagicMock(spec=StarsDisplay)
    mock_stars_display.min_win_score = 90
    coordinator.game.stars_display = mock_stars_display
    coordinator.game.scores = [MagicMock(stars_enabled=True), MagicMock(stars_enabled=True)]

    # Set pending params with stars disabled
    params = GameParams(
        descent_mode="discrete",
        descent_duration_s=120,
        one_round=False,
        min_win_score=0,
        stars=False,
        level=0
    )
    coordinator.set_pending_game_params(params)

    # Apply params
    await coordinator.apply_pending_params()

    # Verify stars display was replaced with NullStarsDisplay
    assert isinstance(coordinator.game.stars_display, NullStarsDisplay)
    # Verify scores were updated
    assert coordinator.game.scores[0].stars_enabled is False
    assert coordinator.game.scores[1].stars_enabled is False


@pytest.mark.asyncio
async def test_apply_pending_params_when_none():
    """Verify that apply_pending_params returns False when no params pending."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()

    # No pending params
    needs_re_setup = await coordinator.apply_pending_params()

    assert needs_re_setup is False
    # Game should not be modified - check that one_round wasn't changed
    coordinator.game.one_round = False  # Set a value
    original_value = coordinator.game.one_round
    await coordinator.apply_pending_params()
    assert coordinator.game.one_round == original_value


@pytest.mark.asyncio
async def test_apply_pending_params_no_re_setup_for_same_descent():
    """Verify that apply_pending_params returns False when descent params don't change."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()
    coordinator.game.rack_metrics = MagicMock()
    coordinator.game.sound_manager = MagicMock()
    coordinator.game.scores = [MagicMock(), MagicMock()]
    coordinator.game.stars_display = NullStarsDisplay()

    # Set current params in the dict
    coordinator.current_setup_params = {
        'descent_mode': 'discrete',
        'descent_duration_s': 120,
    }

    # Set pending params with same descent settings
    params = GameParams(
        descent_mode="discrete",
        descent_duration_s=120,
        one_round=True,
        min_win_score=90,
        stars=False,
        level=1
    )
    coordinator.set_pending_game_params(params)

    # Apply params
    needs_re_setup = await coordinator.apply_pending_params()

    # Should return False because descent_mode and duration didn't change
    assert needs_re_setup is False


@pytest.mark.asyncio
async def test_apply_pending_params_updates_existing_stars():
    """Verify that apply_pending_params updates min_win_score on existing stars display."""
    coordinator = GameCoordinator()
    coordinator.game = MagicMock()
    coordinator.game.rack_metrics = MagicMock()
    coordinator.game.sound_manager = MagicMock()

    # Set up mock game with stars already enabled
    mock_stars_display = MagicMock(spec=StarsDisplay)
    mock_stars_display.min_win_score = 90
    coordinator.game.stars_display = mock_stars_display
    coordinator.game.scores = [MagicMock(stars_enabled=True), MagicMock(stars_enabled=True)]

    # Set pending params with different min_win_score but stars still enabled
    params = GameParams(
        descent_mode="discrete",
        descent_duration_s=120,
        one_round=False,
        min_win_score=360,
        stars=True,
        level=2
    )
    coordinator.set_pending_game_params(params)

    # Apply params
    await coordinator.apply_pending_params()

    # Verify min_win_score was updated on existing stars display
    assert coordinator.game.stars_display.min_win_score == 360
    # Stars display should still be the same mock (not replaced)
    assert coordinator.game.stars_display is mock_stars_display
