"""Unit tests for GameParams configuration."""
import argparse
import pytest
from config.game_params import GameParams


def test_game_params_defaults():
    """Test default values."""
    params = GameParams()
    assert params.descent_mode == "discrete"
    assert params.descent_duration_s == 120
    assert params.one_round is False
    assert params.min_win_score == 0
    assert params.stars is False
    assert params.level == 0


def test_game_params_from_json_full():
    """Test parsing complete JSON payload."""
    json_str = '{"descent_mode":"timed","descent_duration":90,"one_round":true,"min_win_score":90,"stars":true,"level":1}'
    params = GameParams.from_json(json_str)

    assert params.descent_mode == "timed"
    assert params.descent_duration_s == 90
    assert params.one_round is True
    assert params.min_win_score == 90
    assert params.stars is True
    assert params.level == 1


def test_game_params_from_json_partial():
    """Test parsing partial JSON payload (uses defaults for missing fields)."""
    json_str = '{"descent_mode":"timed","level":2}'
    params = GameParams.from_json(json_str)

    assert params.descent_mode == "timed"
    assert params.descent_duration_s == 120  # default
    assert params.one_round is False  # default
    assert params.min_win_score == 0  # default
    assert params.stars is False  # default
    assert params.level == 2


def test_game_params_from_json_empty():
    """Test parsing empty JSON string returns None."""
    assert GameParams.from_json("") is None
    assert GameParams.from_json("   ") is None
    assert GameParams.from_json(None) is None


def test_game_params_from_json_invalid():
    """Test parsing invalid JSON raises exception."""
    with pytest.raises(Exception):  # JSONDecodeError
        GameParams.from_json("not valid json")


def test_game_params_from_args():
    """Test creating from argparse Namespace."""
    args = argparse.Namespace(
        descent_mode="timed",
        descent_duration=180,
        one_round=True,
        min_win_score=100,
        stars=True,
        level=2
    )
    params = GameParams.from_args(args)

    assert params.descent_mode == "timed"
    assert params.descent_duration_s == 180
    assert params.one_round is True
    assert params.min_win_score == 100
    assert params.stars is True
    assert params.level == 2


def test_game_params_string_representation():
    """Test __str__ method."""
    params = GameParams(
        descent_mode="timed",
        descent_duration_s=90,
        one_round=True,
        min_win_score=90,
        stars=True,
        level=1
    )
    s = str(params)
    assert "mode=timed" in s
    assert "duration=90" in s
    assert "one_round=True" in s
    assert "min_win=90" in s
    assert "stars=True" in s
    assert "level=1" in s
