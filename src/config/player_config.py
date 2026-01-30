from dataclasses import dataclass
from typing import Optional
import pygame
from pygame import Color
from config import game_config

@dataclass(frozen=True)
class PlayerConfig:
    """Configuration for a single player's display and behavior."""
    player_id: int
    shield_color: Color
    fader_color: Color
    rack_horizontal_offset: int  # Pixels from center
    selection_reversed: bool  # True if selection grows from right to left
    
    # 2-player flashing logic
    flash_hit_min: int  # Inclusive
    flash_hit_max: int  # Exclusive
    flash_offset: int

    def get_flashing_index(self, global_index: int, is_multiplayer: bool) -> Optional[int]:
        """
        Transform global falling letter index to local rack index.
        Returns None if the letter is not for this player.
        """
        if not is_multiplayer:
            return global_index
            
        if self.flash_hit_min <= global_index < self.flash_hit_max:
            return global_index + self.flash_offset
        return None

    def get_selection_rect(self, select_count: int, letter_width: int,
                          letter_height: int, max_letters: int) -> pygame.Rect:
        """Calculate selection rectangle based on player configuration."""
        if self.selection_reversed:
            # For player 1, start from right side and expand left
            x = letter_width * (max_letters - select_count)
            return pygame.Rect(x, 0, letter_width * select_count, letter_height)
        else:
            # For player 0 or single player, start from left side and expand right
            return pygame.Rect(0, 0, letter_width * select_count, letter_height)


class PlayerConfigManager:
    """Manages player configurations for all players."""

    def __init__(self, letter_width: int):
        self.configs: dict[int, PlayerConfig] = {}
        self._initialize_configs(letter_width)

    def _initialize_configs(self, letter_width: int) -> None:
        # Single Player (ID -1)
        self.configs[-1] = PlayerConfig(
            player_id=-1,
            shield_color=game_config.SHIELD_COLOR_P0,
            fader_color=game_config.FADER_COLOR_P0,
            rack_horizontal_offset=0,
            selection_reversed=False,
            # Single player maps 1:1, but the method handles !is_multiplayer check
            flash_hit_min=0,
            flash_hit_max=999,
            flash_offset=0
        )

        # Player 0
        self.configs[0] = PlayerConfig(
            player_id=0,
            shield_color=game_config.SHIELD_COLOR_P0,
            fader_color=game_config.FADER_COLOR_P0,
            rack_horizontal_offset=-(letter_width * 3),
            selection_reversed=False,
            flash_hit_min=0,
            flash_hit_max=3,
            flash_offset=3
        )

        # Player 1
        self.configs[1] = PlayerConfig(
            player_id=1,
            shield_color=game_config.SHIELD_COLOR_P1,
            fader_color=game_config.FADER_COLOR_P1,
            rack_horizontal_offset=(letter_width * 3),
            selection_reversed=True,
            flash_hit_min=3,
            flash_hit_max=6,
            flash_offset=-3
        )

    def get_config(self, player_id: int) -> PlayerConfig:
        """Get configuration for a specific player."""
        if player_id not in self.configs:
             # Fallback or error? For now fallback to P0 or error
             raise ValueError(f"Unknown player_id: {player_id}")
        return self.configs[player_id]

    def get_single_player_config(self) -> PlayerConfig:
        """Get configuration for single-player mode."""
        return self.configs[-1]
