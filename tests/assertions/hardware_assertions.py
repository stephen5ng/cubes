"""Hardware interaction assertion helpers.

This module provides clean assertion helpers for verifying hardware mock calls
in integration tests, replacing verbose manual inspection of call_args_list.
"""

from typing import Any
from unittest.mock import Mock


def assert_letter_lock_called_with(
    mock_hardware: Any,
    cube_set: int,
    tile_id: str,
    message: str = None
) -> None:
    """Assert letter_lock was called with specific cube_set and tile_id.

    Args:
        mock_hardware: Mock hardware fixture from conftest
        cube_set: Expected cube set ID (0 for P0, 1 for P1)
        tile_id: Expected tile ID
        message: Optional custom error message

    Example:
        assert_letter_lock_called_with(mock_hardware, cube_set=0, tile_id="42")
    """
    matching_calls = [
        c for c in mock_hardware.letter_lock.call_args_list
        if len(c.args) > 2 and c.args[1] == cube_set and c.args[2] == tile_id
    ]

    if not matching_calls:
        if message is None:
            message = (
                f"letter_lock not called with cube_set={cube_set}, tile_id={tile_id}. "
                f"Calls: {mock_hardware.letter_lock.call_args_list}"
            )
        assert False, message


def assert_accept_new_letter_broadcast(
    mock_hardware: Any,
    tile_id: str,
    cube_set_id: int,
    message: str = None
) -> None:
    """Assert accept_new_letter was called to broadcast to a specific cube set.

    Args:
        mock_hardware: Mock hardware fixture from conftest
        tile_id: Expected tile ID being broadcast
        cube_set_id: Expected cube set receiving the broadcast
        message: Optional custom error message

    Example:
        assert_accept_new_letter_broadcast(mock_hardware, tile_id="42", cube_set_id=1)
    """
    matching_calls = [
        c for c in mock_hardware.accept_new_letter.call_args_list
        if len(c.args) > 3 and c.args[2] == tile_id and c.args[3] == cube_set_id
    ]

    if not matching_calls:
        if message is None:
            message = (
                f"accept_new_letter not called with tile_id={tile_id}, cube_set_id={cube_set_id}. "
                f"Calls: {mock_hardware.accept_new_letter.call_args_list}"
            )
        assert False, message


def assert_load_rack_called_for_cube_set(
    mock_hardware: Any,
    cube_set_id: int,
    message: str = None
) -> None:
    """Assert load_rack was called for a specific cube set.

    Args:
        mock_hardware: Mock hardware fixture from conftest
        cube_set_id: Expected cube set ID
        message: Optional custom error message

    Example:
        assert_load_rack_called_for_cube_set(mock_hardware, cube_set_id=0)
    """
    matching_calls = [
        c for c in mock_hardware.load_rack.call_args_list
        if len(c.args) > 2 and c.args[2] == cube_set_id
    ]

    if not matching_calls:
        if message is None:
            message = (
                f"load_rack not called for cube_set_id={cube_set_id}. "
                f"Calls: {mock_hardware.load_rack.call_args_list}"
            )
        assert False, message


def assert_load_rack_not_called_for_cube_set(
    mock_hardware: Any,
    cube_set_id: int,
    message: str = None
) -> None:
    """Assert load_rack was NOT called for a specific cube set.

    Args:
        mock_hardware: Mock hardware fixture from conftest
        cube_set_id: Cube set ID that should not have been called
        message: Optional custom error message

    Example:
        assert_load_rack_not_called_for_cube_set(mock_hardware, cube_set_id=1)
    """
    matching_calls = [
        c for c in mock_hardware.load_rack.call_args_list
        if len(c.args) > 2 and c.args[2] == cube_set_id
    ]

    if matching_calls:
        if message is None:
            message = (
                f"load_rack should NOT have been called for cube_set_id={cube_set_id}, "
                f"but was called {len(matching_calls)} time(s)"
            )
        assert False, message


def assert_guess_tiles_called_with(
    mock_hardware: Any,
    tile_ids: list[str],
    cube_set_id: int,
    player: int,
    message: str = None
) -> None:
    """Assert guess_tiles was called with specific parameters.

    Args:
        mock_hardware: Mock hardware fixture from conftest
        tile_ids: Expected list of tile IDs
        cube_set_id: Expected cube set ID
        player: Expected player ID
        message: Optional custom error message

    Example:
        assert_guess_tiles_called_with(
            mock_hardware,
            tile_ids=["101", "102", "103"],
            cube_set_id=1,
            player=1
        )
    """
    matching_calls = [
        c for c in mock_hardware.guess_tiles.call_args_list
        if (len(c.args) > 3 and
            c.args[1] == [tile_ids] and
            c.args[2] == cube_set_id and
            c.args[3] == player)
    ]

    if not matching_calls:
        if message is None:
            message = (
                f"guess_tiles not called with tile_ids={tile_ids}, "
                f"cube_set_id={cube_set_id}, player={player}. "
                f"Calls: {mock_hardware.guess_tiles.call_args_list}"
            )
        assert False, message
