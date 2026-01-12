"""Test context builders for integration tests."""
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from game.game_state import Game
from testing.fake_mqtt_client import FakeMqttClient
from tests.fixtures.test_helpers import drain_mqtt_queue


@dataclass
class GuessResult:
    """Result of a guess operation in tests."""
    shield_created: bool
    score_change: int
    border_color: Optional[str]
    flash_sent: bool


class IntegrationTestContext:
    """High-level test context for integration tests.

    Encapsulates common setup, assertion, and interaction patterns
    to reduce boilerplate and improve test readability.

    Example:
        ctx = await IntegrationTestContext.create(players=[0])
        result = await ctx.make_guess(["0", "1"], player=0)
        ctx.assert_border_color("0x07E0")  # green
        ctx.assert_flash_sent(cube_id=1)
    """

    def __init__(self, game: Game, mqtt: FakeMqttClient, queue: asyncio.Queue):
        self.game = game
        self.mqtt = mqtt
        self.queue = queue
        self._initial_scores: Dict[int, int] = {}

    @classmethod
    async def create(cls, players: List[int] = [0], **game_kwargs):
        """Create a new test context with game initialized.

        Args:
            players: List of player IDs to initialize
            **game_kwargs: Additional arguments for create_game_with_started_players

        Returns:
            IntegrationTestContext instance ready for testing
        """
        from tests.fixtures.game_factory import create_game_with_started_players
        game, mqtt, queue = await create_game_with_started_players(
            players=players,
            **game_kwargs
        )
        ctx = cls(game, mqtt, queue)
        ctx._capture_initial_state()
        return ctx

    def _capture_initial_state(self):
        """Capture initial state for comparison."""
        for i in range(len(self.game.scores)):
            self._initial_scores[i] = self.game.scores[i].score

    async def make_guess(
        self,
        tile_ids: List[str],
        player: int = 0,
        now_ms: int = 1000
    ) -> GuessResult:
        """Make a guess and return structured result.

        Args:
            tile_ids: List of tile IDs forming the guess
            player: Player making the guess
            now_ms: Timestamp for the guess

        Returns:
            GuessResult with outcome details
        """
        initial_shield_count = len(self.game.shields)
        initial_score = self.game.scores[player].score

        self.mqtt.clear_published()

        # Depending on how guess is triggered.
        # Ideally we use App.guess_tiles directly as it mimics the core logic entry for guesses.
        await self.game._app.guess_tiles(
            tile_ids,
            move_tiles=False,
            player=player,
            now_ms=now_ms
        )
        await asyncio.sleep(0)
        await drain_mqtt_queue(self.mqtt, self.queue)

        shield_created = len(self.game.shields) > initial_shield_count
        score_change = self.game.scores[player].score - initial_score

        # Get border color
        # Note: We need player-based lookup, which app handles
        border_color = self.game._app.get_player_border_color(player)

        # Check for flash
        flash_messages = [m for m in self.mqtt.published_messages if "flash" in m[0]]
        flash_sent = len(flash_messages) > 0

        return GuessResult(
            shield_created=shield_created,
            score_change=score_change,
            border_color=border_color,
            flash_sent=flash_sent
        )

    def assert_score(self, player: int, expected: int, msg: str = ""):
        """Assert player score matches expected value."""
        actual = self.game.scores[player].score
        assert actual == expected, (
            f"{msg}\nPlayer {player} score mismatch: "
            f"expected {expected}, got {actual}"
        )

    def assert_score_change(self, player: int, expected_delta: int):
        """Assert player score changed by expected amount."""
        initial = self._initial_scores[player]
        actual = self.game.scores[player].score
        actual_delta = actual - initial
        assert actual_delta == expected_delta, (
            f"Score change mismatch for player {player}: "
            f"expected +{expected_delta}, got +{actual_delta} "
            f"(initial={initial}, current={actual})"
        )

    def assert_border_color(self, expected_color: str, player: int = 0):
        """Assert player's cube set has expected border color."""
        actual = self.game._app.get_player_border_color(player)
        assert actual == expected_color, (
            f"Border color mismatch for player {player}: expected {expected_color}, got {actual}"
        )

    def assert_flash_sent(self, cube_id: Optional[int] = None):
        """Assert flash message was sent to specified cube (or any cube)."""
        flash_msgs = [m for m in self.mqtt.published_messages if "flash" in m[0]]

        if cube_id is not None:
            cube_flashes = [m for m in flash_msgs if f"cube/{cube_id}/flash" in m[0]]
            assert len(cube_flashes) > 0, (
                f"No flash message sent to cube {cube_id}. "
                f"Flash messages: {[m[0] for m in flash_msgs]}"
            )
        else:
            assert len(flash_msgs) > 0, "No flash messages sent to any cube"

    def assert_shield_created(self, expected_word: str):
        """Assert a shield was created with expected word."""
        shields_with_word = [s for s in self.game.shields if s.letters == expected_word]
        assert len(shields_with_word) > 0, (
            f"No shield created with word '{expected_word}'. "
            f"Shields: {[s.letters for s in self.game.shields]}"
        )
