"""Tests for final score publishing via MQTT."""

import json
import pytest
import pygame
from unittest.mock import patch, AsyncMock, MagicMock
from tests.fixtures.game_factory import create_test_game, async_test


@async_test
async def test_final_score_data_format():
    """Verify final score data is correctly formatted."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100, stars=True)

    # Set up a known score
    game.scores[0].score = 150
    game.start_time_s = 100.0  # Start at 100 seconds

    # Mock the aiomqtt client to capture published data
    published_data = None

    async def mock_publish(topic, payload, retain):
        nonlocal published_data
        if topic == "game/final_score":
            published_data = json.loads(payload)

    with patch('game.game_state.aiomqtt') as mock_aiomqtt:
        # Set up mock client
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.publish = AsyncMock(side_effect=mock_publish)

        mock_aiomqtt.Client.return_value = mock_client

        # Stop the game at 160 seconds (60 second duration)
        await game.stop(160000, exit_code=0)

    # Verify the data was published
    assert published_data is not None, "Final score data should be published"
    assert published_data["score"] == 150
    assert published_data["stars"] == 3  # 150 points = 3 stars (capped at 3)
    assert published_data["exit_code"] == 10  # Win (3 stars earned)
    assert published_data["min_win_score"] == 100
    assert published_data["duration_s"] == 60.0


@async_test
async def test_final_score_with_no_min_win_score():
    """Verify final score data when min_win_score is 0."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=0)

    game.scores[0].score = 50
    game.start_time_s = 100.0

    published_data = None

    async def mock_publish(topic, payload, retain):
        nonlocal published_data
        if topic == "game/final_score":
            published_data = json.loads(payload)

    with patch('game.game_state.aiomqtt') as mock_aiomqtt:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.publish = AsyncMock(side_effect=mock_publish)

        mock_aiomqtt.Client.return_value = mock_client

        await game.stop(130000, exit_code=0)  # 30 second duration

    assert published_data is not None
    assert published_data["score"] == 50
    assert published_data["stars"] == 0  # No min_win_score
    assert published_data["exit_code"] == 0  # No win condition
    assert published_data["min_win_score"] == 0


@async_test
async def test_final_score_on_loss():
    """Verify final score data on game loss (exit code 11)."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100, stars=True)

    game.scores[0].score = 50
    game.start_time_s = 100.0

    published_data = None

    async def mock_publish(topic, payload, retain):
        nonlocal published_data
        if topic == "game/final_score":
            published_data = json.loads(payload)

    with patch('game.game_state.aiomqtt') as mock_aiomqtt:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.publish = AsyncMock(side_effect=mock_publish)

        mock_aiomqtt.Client.return_value = mock_client

        # Simulate loss (exit code 11) at 145 seconds (45 second duration)
        await game.stop(145000, exit_code=11)

    assert published_data is not None
    assert published_data["score"] == 50
    assert published_data["stars"] == 1  # 50 / (100/3) = 1.5, int() = 1
    assert published_data["exit_code"] == 11
    assert published_data["min_win_score"] == 100


@async_test
async def test_final_score_uses_retain():
    """Verify final score is published with retain=True."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=50)

    game.scores[0].score = 60
    game.start_time_s = 100.0

    publish_calls = []

    async def mock_publish(topic, payload, retain):
        publish_calls.append({"topic": topic, "retain": retain})

    with patch('game.game_state.aiomqtt') as mock_aiomqtt:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.publish = AsyncMock(side_effect=mock_publish)

        mock_aiomqtt.Client.return_value = mock_client

        await game.stop(120000, exit_code=0)  # 20 second duration

    # Find the game/final_score publish call
    final_score_calls = [c for c in publish_calls if c["topic"] == "game/final_score"]
    assert len(final_score_calls) > 0, "Final score should be published"
    assert final_score_calls[0]["retain"] is True, "Final score should be retained"


@async_test
async def test_final_score_graceful_broker_failure():
    """Verify game continues even if MQTT broker is unavailable."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=50, stars=True)

    game.scores[0].score = 60
    game.start_time_s = 100.0

    # Simulate broker connection failure
    with patch('game.game_state.aiomqtt') as mock_aiomqtt:
        mock_aiomqtt.Client.side_effect = Exception("Connection refused")

        # Should not raise, just log error
        await game.stop(120000, exit_code=0)

    # Game should have exited with win (60 points = 3.6 stars -> 3 stars)
    assert game.exit_code == 10  # Win (3 stars earned)
    assert not game.running


@async_test
async def test_final_score_connection_params():
    """Verify final score publishes to correct broker address."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=50)

    game.scores[0].score = 60
    game.start_time_s = 100.0

    client_calls = []

    # Create a mock that tracks initialization parameters
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.publish = AsyncMock()

    def mock_client_class(hostname=None, port=None):
        client_calls.append({"hostname": hostname, "port": port})
        return mock_client

    with patch('game.game_state.aiomqtt.Client', side_effect=mock_client_class):
        await game.stop(160000, exit_code=0)

    # Verify correct broker connection
    assert len(client_calls) > 0
    assert client_calls[0]["hostname"] == "localhost"  # Default
    assert client_calls[0]["port"] == 1883  # Main MQTT port
