from typing import List
import logging
from config import game_config
from core import tiles
from core.dictionary import Dictionary
from core.tile_generator import TileGenerator

class RackManager:
    """
    Manages the lifecycle and synchronization of player Racks.
    Handles 'Shared Start' initialization and 'Copy-on-Write' divergence updates.
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
            # Players start with identical tile sets
            self._racks[player].set_tiles(initial_tiles)
            self._racks[player].set_next_letter(next_letter)
            
    def update_next_letter(self, current_letters: str) -> None:
        """Update the pending next letter based on current board state."""
        next_val = self._tile_generator.get_next_letter(current_letters)
        for rack in self._racks:
            rack.set_next_letter(next_val)

    def accept_new_letter(self, new_letter: str, position: int, hit_rack_idx: int, position_offset: int) -> tiles.Tile:
        """Process a new letter landing on a specific rack."""
        hit_rack = self._racks[hit_rack_idx]
        
        target_pos = position + position_offset
        
        # Get the old tile needed for validation/sync *before* replacement
        old_tile = hit_rack.get_tiles()[target_pos]
        
        changed_tile = hit_rack.replace_letter(new_letter, target_pos)
        
        # 3. Synchronize other racks that might share this tile (Shared Start invariant)
        for i, other_rack in enumerate(self._racks):
            if i == hit_rack_idx:
                continue
                
            # Check if this rack holds the OLD tile object
            try:
                other_pos = other_rack.get_tiles().index(old_tile)
                # Found it! It's a shared rack. Update it too.
                other_rack.replace_letter(new_letter, other_pos)
            except ValueError:
                # Diverged rack, doesn't have the old tile. Ignore.
                pass
                
        # 4. Advance RNG for everyone (Single Source of Truth)
        next_gen_letter = self._tile_generator.get_next_letter(hit_rack.letters())
        
        for rack in self._racks:
            rack.set_next_letter(next_gen_letter)
            
        return changed_tile
