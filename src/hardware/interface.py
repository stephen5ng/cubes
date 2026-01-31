from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Optional
import asyncio
from core import tiles

class HardwareInterface(ABC):
    """Abstract interface for hardware interactions (cubes_to_game)."""
    
    @abstractmethod
    def set_guess_tiles_callback(self, callback: Callable[[list[str], bool, int, int], Coroutine[Any, Any, None]]) -> None:
        pass

    @abstractmethod
    def set_start_game_callback(self, callback: Callable[[bool, int, int], Coroutine[Any, Any, None]]) -> None:
        pass

    @abstractmethod
    def get_started_cube_sets(self) -> list[int]:
        pass

    @abstractmethod
    def reset_player_started_state(self) -> None:
        pass

    @abstractmethod
    def add_player_started(self, player_id: int) -> None:
        pass
    
    @abstractmethod
    def set_game_running(self, running: bool) -> None:
        pass

    @abstractmethod
    def has_player_started_game(self, player_id: int) -> bool:
        pass
        
    @abstractmethod
    async def clear_remaining_abc_cubes(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        pass

    @abstractmethod
    async def guess_last_tiles(self, publish_queue: asyncio.Queue, cube_set_id: int, player: int, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def load_rack(self, publish_queue: asyncio.Queue, tiles_with_letters: list[tiles.Tile], cube_set_id: int, player: int, now_ms: int) -> None:
        pass
        
    @abstractmethod
    def set_game_end_time(self, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def unlock_all_letters(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def clear_all_letters(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        pass

    @abstractmethod
    async def clear_all_borders(self, publish_queue: asyncio.Queue, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def accept_new_letter(self, publish_queue: asyncio.Queue, next_letter: str, tile_id: str, cube_set_id: int, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def letter_lock(self, publish_queue: asyncio.Queue, cube_set_id: int, tile_id: Optional[str], now_ms: int) -> bool:
        pass
        
    @abstractmethod
    async def old_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int) -> None:
        pass
        
    @abstractmethod
    async def good_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int, now_ms: int) -> None:
        pass
        
    @abstractmethod
    async def bad_guess(self, publish_queue: asyncio.Queue, word_tile_ids: list[str], cube_set_id: int, player: int) -> None:
        pass
        
    @abstractmethod
    async def guess_tiles(self, publish_queue: asyncio.Queue, word_tile_ids: list[list[str]], cube_set_id: int, player: int, now_ms: int) -> None:
        pass

    @abstractmethod
    def remove_player_from_abc_tracking(self, player_id: int) -> None:
        """Remove a player from ABC manager tracking."""
        pass
