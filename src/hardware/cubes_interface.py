from typing import Any, Callable, Coroutine, Optional
import asyncio
from core import tiles
from hardware import cubes_to_game
from hardware.cubes_to_game import state as ctg_state
from hardware.interface import HardwareInterface

class CubesHardwareInterface(HardwareInterface):
    """Concrete implementation of HardwareInterface using cubes_to_game."""
    
    def set_guess_tiles_callback(self, callback: Callable[[list[str], bool, int, int], Coroutine[Any, Any, None]]) -> None:
        cubes_to_game.set_guess_tiles_callback(callback)

    def set_start_game_callback(self, callback: Callable[[bool, int, int], Coroutine[Any, Any, None]]) -> None:
        cubes_to_game.set_start_game_callback(callback)

    def get_started_cube_sets(self) -> list[int]:
        return cubes_to_game.get_started_cube_sets()

    def reset_player_started_state(self) -> None:
        cubes_to_game.reset_player_started_state()

    def add_player_started(self, player_id: int) -> None:
        cubes_to_game.add_player_started(player_id)
    
    def set_game_running(self, running: bool) -> None:
        cubes_to_game.set_game_running(running)

    def has_player_started_game(self, player_id: int) -> bool:
        return cubes_to_game.has_player_started_game(player_id)
        
    async def clear_remaining_abc_cubes(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        await cubes_to_game.clear_remaining_abc_cubes(publish_queue, now_ms)

    async def guess_last_tiles(self, publish_queue: asyncio.Queue, cube_set_id: int, player: int, now_ms: int) -> None:
        await cubes_to_game.guess_last_tiles(publish_queue, cube_set_id, player, now_ms)
        
    async def load_rack(self, publish_queue: asyncio.Queue, tiles_with_letters: list[tiles.Tile], cube_set_id: int, player: int, now_ms: int) -> None:
        await cubes_to_game.load_rack(publish_queue, tiles_with_letters, cube_set_id, player, now_ms)
        
    def set_game_end_time(self, now_ms: int) -> None:
        cubes_to_game.set_game_end_time(now_ms)
        
    async def unlock_all_letters(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        await cubes_to_game.unlock_all_letters(publish_queue, now_ms)
        
    async def clear_all_borders(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        await cubes_to_game.clear_all_borders(publish_queue, now_ms)
        
    async def accept_new_letter(self, publish_queue: asyncio.Queue, next_letter: str, tile_id: str, cube_set_id: int, now_ms: int) -> None:
        await cubes_to_game.accept_new_letter(publish_queue, next_letter, tile_id, cube_set_id, now_ms)
        
    async def letter_lock(self, publish_queue: asyncio.Queue, cube_set_id: int, tile_id: Optional[str], now_ms: int) -> bool:
        return await cubes_to_game.letter_lock(publish_queue, cube_set_id, tile_id, now_ms)
        
    async def old_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int) -> None:
        await cubes_to_game.old_guess(publish_queue, word_tile_ids, cube_set_id, player)
        
    async def good_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int, now_ms: int) -> None:
        await cubes_to_game.good_guess(publish_queue, word_tile_ids, cube_set_id, player, now_ms)
        
    async def bad_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int) -> None:
        await cubes_to_game.bad_guess(publish_queue, word_tile_ids, cube_set_id, player)
        
    async def guess_tiles(self, publish_queue: asyncio.Queue, word_tile_ids: list[list[str]], cube_set_id: int, player: int, now_ms: int) -> None:
        await cubes_to_game.guess_tiles(publish_queue, word_tile_ids, cube_set_id, player, now_ms)

    def remove_player_from_abc_tracking(self, player_id: int) -> None:
        if player_id in ctg_state.abc_manager.player_abc_cubes:
             del ctg_state.abc_manager.player_abc_cubes[player_id]

    def get_cube_set_border_color(self, cube_set_id: int) -> Optional[str]:
        """Get the current border color for a cube set.

        Args:
            cube_set_id: Cube set identifier (0 for P0/cubes 1-6, 1 for P1/cubes 11-16)

        Returns:
            Hex color string (e.g., "0x07E0" for green) or None if not set

        Raises:
            IndexError: If cube_set_id is invalid

        Note:
            Primarily for testing - allows verification of visual feedback
            without accessing internal state.
        """
        if cube_set_id < 0 or cube_set_id >= len(ctg_state.cube_set_managers):
            raise IndexError(f"Invalid cube set ID: {cube_set_id}")
        return ctg_state.cube_set_managers[cube_set_id].border_color
