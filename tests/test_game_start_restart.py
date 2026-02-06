"""Test game/start MQTT restart functionality."""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from mqtt.mqtt_coordinator import MQTTCoordinator
from game.game_state import Game
from game.game_coordinator import GameCoordinator
from core.app import App
from game.components import StarsDisplay, NullStarsDisplay


@pytest.mark.asyncio
async def test_game_start_restarts_running_game():
    """Verify that game/start stops and restarts a running game."""
    # Create mock game and app
    game = MagicMock()
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()

    # Set up scores (level 0 should reset scores to 0)
    # start_cubes will reset these, so create realistic mock
    class MockScore:
        def __init__(self):
            self.score = 100
        def start(self):
            self.score = 0
        def draw(self):
            pass

    mock_score1 = MockScore()
    mock_score2 = MockScore()
    game.scores = [mock_score1, mock_score2]

    async def mock_start_cubes(now_ms):
        # Simulate start_cubes resetting scores
        for score in game.scores:
            score.start()

    game.start_cubes = AsyncMock(side_effect=mock_start_cubes)
    game.stars_display = MagicMock(spec=StarsDisplay)

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message (no payload = level 0)
    await coordinator.handle_message("game/start", "", 1000)

    # Verify stop was called (game was running)
    game.stop.assert_called_once_with(1000, 0)
    # Verify start_cubes was called (game restarted)
    game.start_cubes.assert_called_once_with(1000)
    # Verify stars were reset
    game.stars_display.reset.assert_called_once()

    # Verify scores were NOT restored (level 0 resets scores)
    assert mock_score1.score == 0
    assert mock_score2.score == 0
    # Verify baseline was NOT set (no score preservation at level 0)
    game.stars_display.set_baseline_score.assert_not_called()


@pytest.mark.asyncio
async def test_game_start_starts_non_running_game():
    """Verify that game/start starts a game that's not running."""
    # Create mock game and app
    game = MagicMock()
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as not running
    game.running = False
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()
    game.stars_display = MagicMock(spec=StarsDisplay)

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message
    await coordinator.handle_message("game/start", "", 1000)

    # Verify stop was NOT called (game was not running)
    game.stop.assert_not_called()
    # Verify start_cubes was called (game started)
    game.start_cubes.assert_called_once_with(1000)
    # Verify stars were reset
    game.stars_display.reset.assert_called_once()


@pytest.mark.asyncio
async def test_game_start_with_json_params():
    """Verify that game/start with JSON payload stores and applies params."""
    # Create mock game and app
    game = MagicMock()
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()
    game.stars_display = MagicMock(spec=StarsDisplay)

    # Set up scores with realistic behavior
    class MockScore:
        def __init__(self, initial_score):
            self.score = initial_score
        def start(self):
            self.score = 0
        def draw(self):
            pass

    mock_score1 = MockScore(100)
    mock_score2 = MockScore(50)
    game.scores = [mock_score1, mock_score2]

    async def mock_start_cubes(now_ms):
        # Simulate start_cubes resetting scores
        for score in game.scores:
            score.start()

    game.start_cubes = AsyncMock(side_effect=mock_start_cubes)

    # Create GameCoordinator mock
    game_coordinator = MagicMock(spec=GameCoordinator)
    game_coordinator.set_pending_game_params = MagicMock()
    game_coordinator.apply_pending_params = AsyncMock()

    # Create coordinator with game_coordinator reference
    coordinator = MQTTCoordinator(game, app, publish_queue, game_coordinator)

    # Send game/start message with JSON payload (level 1)
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
    # Verify stars were reset
    game.stars_display.reset.assert_called_once()

    # Verify scores were restored (level > 0 preserves score)
    assert mock_score1.score == 100
    assert mock_score2.score == 50
    # Verify baseline was set so stars track points earned in current level
    game.stars_display.set_baseline_score.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_game_start_with_invalid_json():
    """Verify that game/start with invalid JSON logs warning but still restarts."""
    # Create mock game and app
    game = MagicMock()
    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Set up game as running
    game.running = True
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()
    game.stars_display = MagicMock(spec=StarsDisplay)

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message with invalid JSON payload
    # Should still restart despite invalid JSON
    await coordinator.handle_message("game/start", b"invalid json", 1000)

    # Verify stop and start_cubes were still called
    game.stop.assert_called_once_with(1000, 0)
    game.start_cubes.assert_called_once_with(1000)
    # Verify stars were still reset
    game.stars_display.reset.assert_called_once()


@pytest.mark.asyncio
async def test_game_start_resets_stars_display():
    """Verify that game/start resets the stars display."""
    # Create mock game with a real StarsDisplay
    game = MagicMock()  # Don't use spec=Game to avoid attribute errors
    game.running = True
    game.stop = AsyncMock()
    game.start_cubes = AsyncMock()
    game.scores = []  # Empty scores list for level 0

    # Create a real StarsDisplay to verify reset is called
    mock_stars = MagicMock(spec=StarsDisplay)
    game.stars_display = mock_stars

    app = MagicMock(spec=App)
    publish_queue = asyncio.Queue()

    # Create coordinator
    coordinator = MQTTCoordinator(game, app, publish_queue)

    # Send game/start message
    await coordinator.handle_message("game/start", "", 1000)

    # Verify stars reset was called
    mock_stars.reset.assert_called_once()

    # Verify stop and start_cubes were still called
    game.stop.assert_called_once_with(1000, 0)
    game.start_cubes.assert_called_once_with(1000)
