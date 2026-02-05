"""Test game/start MQTT restart functionality."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from mqtt.mqtt_coordinator import MQTTCoordinator
from game.game_state import Game
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
