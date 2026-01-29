
import pytest
from unittest.mock import MagicMock, patch
from game.components import Score
from config import game_config
from config.game_config import SCREEN_WIDTH

class MockRackMetrics:
    LETTER_SIZE = 20

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.player_count = 1
    return app

def test_score_initialization(mock_app):
    """Verify basic score initialization."""
    pygame_init_mock = MagicMock()
    with patch('pygame.init', pygame_init_mock), \
         patch('pygame.freetype.SysFont') as mock_font_cls:
        
        score = Score(mock_app, 0, MockRackMetrics(), stars_enabled=False)
        score = Score(mock_app, 0, MockRackMetrics(), stars_enabled=False)
        assert score.score == 0
        assert score.player == 0
        
        # Verify default font size
        mock_font_cls.assert_called_with(game_config.FONT, MockRackMetrics.LETTER_SIZE)

def test_score_position_single_player_no_stars(mock_app):
    """Verify score is centered when stars are disabled."""
    with patch('pygame.freetype.SysFont') as mock_font_cls:
        # Setup mock font and surface
        mock_font = mock_font_cls.return_value
        mock_surface = MagicMock()
        mock_surface.get_width.return_value = 100
        mock_font.render.return_value = (mock_surface, MagicMock())

        score = Score(mock_app, 0, MockRackMetrics(), stars_enabled=False)
        
        # Center: SCREEN_WIDTH/2 - width/2
        expected_x = int(SCREEN_WIDTH/2 - 100/2)
        assert score.pos[0] == expected_x
        assert score.pos[1] == 0

def test_score_position_single_player_with_stars(mock_app):
    """Verify score is right-aligned when stars are enabled."""
    with patch('pygame.freetype.SysFont') as mock_font_cls:
        # Setup mock font and surface
        mock_font = mock_font_cls.return_value
        mock_surface = MagicMock()
        mock_surface.get_width.return_value = 100
        # Mock height for vertical centering calc
        # rack_metrics.LETTER_SIZE = 20
        # star_height = int(20 * 0.7 * 1.2) = 16
        # If text height is 10, then pos[1] should be (16 - 10) // 2 = 3
        mock_surface.get_height.return_value = 10
        mock_font.render.return_value = (mock_surface, MagicMock())

        score = Score(mock_app, 0, MockRackMetrics(), stars_enabled=True)
        
        # Verify reduced font size
        # 20 * 0.8 = 16
        mock_font_cls.assert_called_with(game_config.FONT, 16)
        
        # Right: SCREEN_WIDTH - width - 10
        expected_x = int(SCREEN_WIDTH - 100 - 10)
        assert score.pos[0] == expected_x
        # Expect dynamic nudge down
        # (16 - 10) // 2 = 3
        assert score.pos[1] == 3

def test_score_position_multiplayer(mock_app):
    """Verify score position in multiplayer (split screen)."""
    mock_app.player_count = 2
    with patch('pygame.freetype.SysFont') as mock_font_cls:
        mock_font = mock_font_cls.return_value
        mock_surface = MagicMock()
        mock_surface.get_width.return_value = 100
        mock_font.render.return_value = (mock_surface, MagicMock())

        # Player 0
        score_p0 = Score(mock_app, 0, MockRackMetrics(), stars_enabled=False)
        # x = SCREEN_WIDTH/3 * (0+1) = SCREEN_WIDTH/3
        expected_x_p0 = int((SCREEN_WIDTH/3) - 100/2)
        assert score_p0.pos[0] == expected_x_p0

        # Player 1
        score_p1 = Score(mock_app, 1, MockRackMetrics(), stars_enabled=False)
        # x = SCREEN_WIDTH/3 * (1+1) = 2*SCREEN_WIDTH/3
        expected_x_p1 = int((2*SCREEN_WIDTH/3) - 100/2)
        assert score_p1.pos[0] == expected_x_p1
