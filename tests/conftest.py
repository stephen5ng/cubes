import sys
import os
import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

# Ensure src and project root are in the python path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def pytest_addoption(parser):
    parser.addoption("--visual", action="store_true", default=False, help="Run tests with visual feedback")

def pytest_configure(config):
    # Set SDL to dummy driver for headless tests unless --visual is requested
    if config.getoption("--visual"):
        os.environ["VISUAL_MODE"] = "1"
        # If visual mode is requested, ensure no dummy driver
        os.environ.pop("SDL_VIDEODRIVER", None)
    else:
        os.environ["VISUAL_MODE"] = "0"
        if "SDL_VIDEODRIVER" not in os.environ:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            
    # Suppress specific deprecation warnings that are out of our control
    config.addinivalue_line("filterwarnings", "ignore:pkg_resources is deprecated as an API:DeprecationWarning")
    # Broaden filter for declare_namespace to catch messages with special chars
    config.addinivalue_line("filterwarnings", r"ignore:.*declare_namespace.*:DeprecationWarning")

@pytest.fixture
def mock_hardware():
    """
    Fixture that patches all common cubes_to_game functions.
    Returns a namespace object with the mocks.
    """
    with patch('hardware.cubes_to_game.letter_lock', new_callable=AsyncMock) as letter_lock, \
         patch('hardware.cubes_to_game.accept_new_letter', new_callable=AsyncMock) as accept_new_letter, \
         patch('hardware.cubes_to_game.load_rack', new_callable=AsyncMock) as load_rack, \
         patch('hardware.cubes_to_game.guess_tiles', new_callable=AsyncMock) as guess_tiles, \
         patch('hardware.cubes_to_game.has_player_started_game') as has_player_started_game:
        
        # Default behavior for sync mocks
        has_player_started_game.return_value = True 
        
        yield SimpleNamespace(
            letter_lock=letter_lock,
            accept_new_letter=accept_new_letter,
            load_rack=load_rack,
            guess_tiles=guess_tiles,
            has_player_started_game=has_player_started_game
        )
