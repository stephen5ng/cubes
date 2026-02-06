"""Test game/start MQTT restart functionality."""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from mqtt.mqtt_coordinator import MQTTCoordinator
from game.game_state import Game
from game.game_coordinator import GameCoordinator
from core.app import App


@pytest.mark.asyncio
async def test_game_start_restarts_running_game():
    """Verify that game/start stops and restarts a running game."""
    # Create mock game and app
    game = MagicMock(spec=Game)
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message
    await coordinator.handle_message("game/start", "", 1000)

    # Verify stop was called (game was running)
    game.stop.assert_called_once_with(1000, 0)
    # Verify start_cubes was called (game restarted)
    game.start_cubes.assert_called_once_with(1000)


@pytest.mark.asyncio
async def test_game_start_starts_non_running_game():
    """Verify that game/start starts a game that's not running."""
    # Create mock game and app
    game = MagicMock(spec=Game)
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as not running
    game.running = False
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message
    await coordinator.handle_message("game/start", "", 1000)

    # Verify stop was NOT called (game was not running)
    game.stop.assert_not_called()
    # Verify start_cubes was called (game started)
    game.start_cubes.assert_called_once_with(1000)


@pytest.mark.asyncio
async def test_game_start_with_json_params():
    """Verify that game/start with JSON payload stores and applies params."""
    # Create mock game and app
    game = MagicMock(spec=Game)
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()

    # Create GameCoordinator mock
    game_coordinator = MagicMock(spec=GameCoordinator)
    game_coordinator.set_pending_game_params = MagicMock()
    game_coordinator.apply_pending_params = AsyncMock()

    # Create coordinator with game_coordinator reference
    coordinator = MQTTCoordinator(game, app, publish_queue, game_coordinator)

    # Send game/start message with JSON payload
    payload = json.dumps({
        "descent_mode": "timed",
        "descent_duration": 180,
        "one_round": False,
        "min_win_score": 90,
        "stars": True,
        "level": 1
    })
    await coordinator.handle_message("game/start", payload, 1000)

    # Verify params were stored and applied
    game_coordinator.set_pending_game_params.assert_called_once()
    params = game_coordinator.set_pending_game_params.call_args[0][0]
    assert params.descent_mode == "timed"
    assert params.descent_duration_s == 180
    assert params.one_round is False
    assert params.min_win_score == 90
    assert params.stars is True
    assert params.level == 1

    # Verify apply_pending_params was called
    game_coordinator.apply_pending_params.assert_called_once()

    # Verify stop and start_cubes were still called
    game.stop.assert_called_once_with(1000, 0)
    game.start_cubes.assert_called_once_with(1000)


@pytest.mark.asyncio
async def test_game_start_with_invalid_json():
    """Verify that game/start with invalid JSON logs warning but still restarts."""
    # Create mock game and app
    game = MagicMock(spec=Game)
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message with invalid JSON payload
    # Should still restart despite invalid JSON
    await coordinator.handle_message("game/start", b"invalid json", 1000)

    # Verify stop and start_cubes were still called
    game.stop.assert_called_once_with(1000, 0)
    game.start_cubes.assert_called_once_with(1000)
