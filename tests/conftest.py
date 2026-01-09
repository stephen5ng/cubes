import sys
import os

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
