from typing import List
import logging
from config import game_config
from core import tiles
from core.dictionary import Dictionary
from core.tile_generator import TileGenerator

class RackManager:
    """
    Manages player racks with a shared letter pool.

    GAME RULE: Both players always have the same set of letters (fair competition),
    but can arrange tiles in different orders (independent strategy).

    - When a letter is caught, it's added to BOTH players' pools simultaneously
    - Players reorder tiles independently via guess_tiles()
    - Tile IDs (0-5) are stable identifiers that track letters across racks
    """
    def __init__(self, dictionary: Dictionary, tile_generator: TileGenerator):
        self._dictionary = dictionary
        self._tile_generator = tile_generator
        self._racks: List[tiles.Rack] = [
            tiles.Rack('?' * game_config.MAX_LETTERS) for _ in range(game_config.MAX_PLAYERS)
        ]

    def get_rack(self, player_idx: int) -> tiles.Rack:
        return self._racks[player_idx]

    def initialize_racks_for_fair_play(self) -> None:
        """
        Initialize all racks with identical tiles for competitive fairness.
        """
        initial_rack = self._dictionary.get_rack()
        initial_tiles = initial_rack.get_tiles()
        
        initial_letters = "".join(t.letter for t in initial_tiles)
        next_letter = self._tile_generator.get_next_letter(initial_letters)
        
        for player in range(game_config.MAX_PLAYERS):
            # Create new Tile objects for each rack (same letters/IDs, distinct objects)
            # Each player gets the same letter pool but independent tile objects
            player_tiles = [tiles.Tile(t.letter, t.id) for t in initial_tiles]
            self._racks[player].set_tiles(player_tiles)
            self._racks[player].set_next_letter(next_letter)

    def update_next_letter(self, current_letters: str) -> None:
        """Update the pending next letter based on current board state."""
        next_val = self._tile_generator.get_next_letter(current_letters)
        for rack in self._racks:
            rack.set_next_letter(next_val)

    def accept_new_letter(self, new_letter: str, position: int, hit_rack_idx: int, position_offset: int) -> tiles.Tile:
        """
        Add a new letter to the shared pool at a specific tile ID.

        Since both players share the same letter pool, this updates ALL racks
        at the tile ID that was hit, ensuring both players get the same letter.
        """
        hit_rack = self._racks[hit_rack_idx]
        target_pos = position + position_offset

        # Replace letter at the hit position
        changed_tile = hit_rack.replace_letter(new_letter, target_pos)

        # Sync the same letter to all other racks (shared pool invariant)
        for rack in self._racks:
            if rack is hit_rack:
                continue
            # Find where this tile ID lives in the other rack (may be different position)
            other_pos = rack.id_to_position(changed_tile.id)
            rack.replace_letter(new_letter, other_pos)

        # Update next letter for all players
        next_letter = self._tile_generator.get_next_letter(hit_rack.letters())
        for rack in self._racks:
            rack.set_next_letter(next_letter)

        return changed_tile
