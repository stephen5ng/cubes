import pytest
from unittest.mock import MagicMock
from core.app import App
from core.dictionary import Dictionary

# Unit tests for private logic in App

def test_map_position_to_rack_1_player():
    """Verify mapping for 1-player mode (default)."""
    # Setup minimal App
    # We mock dependencies to avoid full initialization
    mock_queue = MagicMock()
    mock_dict = MagicMock()
    app = App(mock_queue, mock_dict)
    app.player_count = 1
    
    # Test typical positions 0-6
    for pos in range(7):
        hit_rack, offset = app._map_position_to_rack(pos)
        assert hit_rack == 0, f"Pos {pos} should map to internal rack 0"
        assert offset == 0, f"Pos {pos} should have offset 0"

def test_map_position_to_rack_2_player():
    """Verify mapping for 2-player mode."""
    mock_queue = MagicMock()
    mock_dict = MagicMock()
    app = App(mock_queue, mock_dict)
    app.player_count = 2
    
    # Player 0 Zone (0, 1, 2)
    # Should map to Rack 0, Offset 0
    for pos in [0, 1, 2]:
        hit_rack, offset = app._map_position_to_rack(pos)
        assert hit_rack == 0, f"Pos {pos} should map to Rack 0"
        assert offset == 0, f"Pos {pos} should have offset 0"
        
    # Player 1 Zone (3, 4, 5)
    # Should map to Rack 1, Offset -3
    # e.g. Pos 3 -> Index 0. (3 + (-3) = 0)
    for pos in [3, 4, 5]:
        hit_rack, offset = app._map_position_to_rack(pos)
        assert hit_rack == 1, f"Pos {pos} should map to Rack 1"
        assert offset == -3, f"Pos {pos} should have offset -3"
