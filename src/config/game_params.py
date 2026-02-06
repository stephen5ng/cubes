"""Game parameter configuration for MQTT-based game control."""
import argparse
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class GameParams:
    """Configuration parameters for a game instance.

    These parameters can be changed between games via MQTT game/start messages.
    """
    descent_mode: str = "discrete"
    descent_duration_s: int = 120
    one_round: bool = False
    min_win_score: int = 0
    stars: bool = False
    level: int = 0

    @classmethod
    def from_json(cls, json_str: str) -> Optional['GameParams']:
        """Create GameParams from JSON string.

        Args:
            json_str: JSON string containing game parameters

        Returns:
            GameParams instance, or None if json_str is empty/None

        Raises:
            json.JSONDecodeError: If json_str is invalid JSON
        """
        if not json_str or json_str.strip() == "":
            return None

        data = json.loads(json_str)

        return cls(
            descent_mode=data.get('descent_mode', 'discrete'),
            descent_duration_s=data.get('descent_duration', 120),
            one_round=data.get('one_round', False),
            min_win_score=data.get('min_win_score', 0),
            stars=data.get('stars', False),
            level=data.get('level', 0)
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'GameParams':
        """Create GameParams from argparse Namespace.

        Args:
            args: Parsed command-line arguments

        Returns:
            GameParams instance with values from args
        """
        return cls(
            descent_mode=args.descent_mode,
            descent_duration_s=args.descent_duration,
            one_round=args.one_round,
            min_win_score=args.min_win_score,
            stars=args.stars,
            level=args.level
        )

    def __str__(self) -> str:
        """Return string representation for logging."""
        return (f"GameParams(mode={self.descent_mode}, duration={self.descent_duration_s}, "
                f"one_round={self.one_round}, min_win={self.min_win_score}, "
                f"stars={self.stars}, level={self.level})")
