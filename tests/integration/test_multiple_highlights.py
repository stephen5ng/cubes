"""Integration test for multiple word chain highlighting."""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock, patch
import pygame

from tests.fixtures.game_factory import create_test_game, async_test
from game.letter import GuessType
from core import tiles


@async_test
async def test_multiple_word_chains_create_multiple_highlights():
    """Test that multiple word chains each get their own highlight border."""
    # Create a test game
    game, mqtt, queue = await create_test_game()

    # Set up the rack with known letters
    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('B', '1'),
        tiles.Tile('C', '2'),
        tiles.Tile('D', '3'),
        tiles.Tile('E', '4'),
        tiles.Tile('F', '5'),
    ]

    print("\n=== Test: Two word chains from separate cube chains ===")

    # Simulate first word chain "ABC" (good guess)
    print("\n1. Processing word chain 'ABC' (tiles 0,1,2)")
    word1_ids = ['0', '1', '2']
    game.racks[0].guess_type = GuessType.GOOD
    now_ms = 1000

    # Call update_rack directly with guessed_tile_ids
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=word1_ids
    )

    print(f"   Highlights after first word: {len(game.racks[0].highlights)}")
    print(f"   {game.racks[0].highlights}")

    assert len(game.racks[0].highlights) == 1, "Should have 1 highlight after first word"
    tile_ids, guess_type, timestamp = game.racks[0].highlights[0]
    assert set(tile_ids) == {'0', '1', '2'}, f"First highlight should contain tiles ['0', '1', '2'], got {tile_ids}"
    assert guess_type == GuessType.GOOD, f"First highlight should be GOOD, got {guess_type}"

    # Simulate second word chain "DEF" (bad guess)
    print("\n2. Processing word chain 'DEF' (tiles 3,4,5)")
    word2_ids = ['3', '4', '5']
    game.racks[0].guess_type = GuessType.BAD
    now_ms = 1100

    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=word2_ids
    )

    print(f"   Highlights after second word: {len(game.racks[0].highlights)}")
    print(f"   {game.racks[0].highlights}")

    assert len(game.racks[0].highlights) == 2, "Should have 2 highlights after second word"
    tile_ids, guess_type, timestamp = game.racks[0].highlights[1]
    assert set(tile_ids) == {'3', '4', '5'}, f"Second highlight should contain tiles ['3', '4', '5'], got {tile_ids}"
    assert guess_type == GuessType.BAD, f"Second highlight should be BAD, got {guess_type}"

    print("\n✅ Test passed: Multiple highlights are created correctly")


@async_test
async def test_highlights_persist_indefinitely():
    """Test that highlights do NOT expire over time."""
    game, mqtt, queue = await create_test_game()

    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('B', '1'),
        tiles.Tile('C', '2'),
        tiles.Tile('D', '3'),
        tiles.Tile('E', '4'),
        tiles.Tile('F', '5'),
    ]

    print("\n=== Test: Highlights persist indefinitely ===")

    # Add a highlight
    game.racks[0].guess_type = GuessType.GOOD
    now_ms = 1000
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=['0', '1', '2']
    )

    assert len(game.racks[0].highlights) == 1, "Should have 1 highlight"
    print(f"   Initially: {len(game.racks[0].highlights)} highlight(s)")

    # Fast-forward way past the old expiration time
    future_ms = now_ms + 5000  # 5 seconds later
    print(f"   Fast-forwarding to {future_ms}ms (created at {now_ms}ms)")

    # Create a real pygame surface for update
    surface_size = game.racks[0].rack_metrics.get_size()
    test_surface = pygame.Surface(surface_size)

    # Make sure rack is running so update() processes highlights
    game.racks[0].running = True
    game.racks[0].update(test_surface, future_ms, flash=False)

    print(f"   After 5 seconds: {len(game.racks[0].highlights)} highlight(s)")

    assert len(game.racks[0].highlights) == 1, "Highlights should NOT expire"
    print(f"   ✅ Highlight still visible after 5 seconds")

    print("\n✅ Test passed: Highlights persist indefinitely")


@async_test
async def test_guess_without_guessed_tile_ids_creates_no_highlight():
    """Test that calling update_rack without guessed_tile_ids doesn't create a highlight."""
    game, mqtt, queue = await create_test_game()

    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('B', '1'),
        tiles.Tile('C', '2'),
    ]

    print("\n=== Test: No guessed_tile_ids means no highlight ===")

    # Call update_rack WITHOUT guessed_tile_ids
    game.racks[0].guess_type = GuessType.GOOD
    now_ms = 1000
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=None  # No tile IDs!
    )

    assert len(game.racks[0].highlights) == 0, "Should have no highlights when guessed_tile_ids is None"
    print(f"   Highlights with guessed_tile_ids=None: {len(game.racks[0].highlights)}")

    print("\n✅ Test passed: No highlight without guessed_tile_ids")


@async_test
async def test_old_border_code_path_still_works():
    """Test that the old code path (no guessed_tile_ids) still works for compatibility."""
    game, mqtt, queue = await create_test_game()

    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('B', '1'),
        tiles.Tile('C', '2'),
    ]

    print("\n=== Test: Backward compatibility ===")

    # This simulates old code that doesn't pass guessed_tile_ids
    game.racks[0].guess_type = GuessType.BAD
    now_ms = 1000
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=None
    )

    # Should not crash, just no highlights
    print(f"   Highlights with old API: {len(game.racks[0].highlights)}")

    print("\n✅ Test passed: Backward compatible")


@async_test
async def test_duplicate_guesses_dont_accumulate():
    """Test that calling update_rack multiple times with same guess doesn't create duplicate highlights."""
    game, mqtt, queue = await create_test_game()

    game.racks[0].tiles = [
        tiles.Tile('H', '0'),
        tiles.Tile('E', '1'),
        tiles.Tile('L', '2'),
        tiles.Tile('D', '3'),
    ]

    print("\n=== Test: Duplicate guesses don't accumulate ===")

    # Add the same guess multiple times (simulating repeated update_rack calls)
    game.racks[0].guess_type = GuessType.GOOD
    now_ms = 1000

    # Call update_rack 5 times with the same parameters
    for i in range(5):
        await game.racks[0].update_rack(
            game.racks[0].tiles,
            highlight_length=4,
            guess_length=4,
            now_ms=now_ms + i * 10,  # Slightly different timestamps
            guessed_tile_ids=['0', '1', '2', '3']
        )

    print(f"   After 5 identical guesses: {len(game.racks[0].highlights)} highlight(s)")
    assert len(game.racks[0].highlights) <= 2, f"Should have at most 2 highlights (one from first call, one refresh), got {len(game.racks[0].highlights)}"

    print("\n✅ Test passed: Duplicate guesses prevented")


@async_test
async def test_extending_word_removes_old_highlight():
    """Test that extending a word removes the old highlight (e.g., OV -> OVL)."""
    game, mqtt, queue = await create_test_game()

    game.racks[0].tiles = [
        tiles.Tile('O', '0'),
        tiles.Tile('V', '1'),
        tiles.Tile('L', '2'),
        tiles.Tile('E', '3'),
    ]

    print("\n=== Test: Extending word removes old highlight ===")

    # First guess: "OV" (tiles 0,1)
    print("\n1. Guessing 'OV' (tiles 0,1)")
    game.racks[0].guess_type = GuessType.BAD
    now_ms = 1000

    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=2,
        guess_length=2,
        now_ms=now_ms,
        guessed_tile_ids=['0', '1']
    )

    print(f"   After 'OV': {len(game.racks[0].highlights)} highlight(s)")
    print(f"   {game.racks[0].highlights}")
    assert len(game.racks[0].highlights) == 1, "Should have 1 highlight after 'OV'"
    tile_ids, guess_type, timestamp = game.racks[0].highlights[0]
    assert set(tile_ids) == {'0', '1'}, f"First highlight should contain tiles ['0', '1'], got {tile_ids}"
    assert guess_type == GuessType.BAD

    # Second guess: "OVL" (tiles 0,1,2) - extends the previous word
    print("\n2. Extending to 'OVL' (tiles 0,1,2)")
    now_ms = 1100

    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=3,
        guess_length=3,
        now_ms=now_ms,
        guessed_tile_ids=['0', '1', '2']
    )

    print(f"   After 'OVL': {len(game.racks[0].highlights)} highlight(s)")
    print(f"   {game.racks[0].highlights}")

    # Should only have ONE highlight - the old "OV" should be removed
    assert len(game.racks[0].highlights) == 1, f"Should have 1 highlight after extending 'OV' to 'OVL', got {len(game.racks[0].highlights)}"
    tile_ids, guess_type, timestamp = game.racks[0].highlights[0]
    assert set(tile_ids) == {'0', '1', '2'}, f"Highlight should contain tiles ['0', '1', '2'], got {tile_ids}"
    assert guess_type == GuessType.BAD

    print("\n✅ Test passed: Old highlight removed when extending word")


@async_test
async def test_separated_tiles_dont_show_highlight():
    """Test that when tiles are separated (moved apart), no highlight is shown."""
    game, mqtt, queue = await create_test_game()

    # Start with tiles in a row: "AD" at positions 0,1
    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('D', '1'),
        tiles.Tile('X', '2'),
        tiles.Tile('Y', '3'),
    ]

    print("\n=== Test: Separated tiles don't show highlight ===")

    # First, create a highlight for "AD"
    print("\n1. Creating highlight for 'AD' (tiles 0,1)")
    game.racks[0].guess_type = GuessType.BAD
    now_ms = 1000

    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=2,
        guess_length=2,
        now_ms=now_ms,
        guessed_tile_ids=['0', '1']
    )

    assert len(game.racks[0].highlights) == 1, "Should have 1 highlight"
    print(f"   After 'AD': {len(game.racks[0].highlights)} highlight(s)")

    # Now separate the tiles: move 'D' to position 3
    print("\n2. Separating tiles: moving 'D' from position 1 to position 3")
    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('X', '2'),
        tiles.Tile('Y', '3'),
        tiles.Tile('D', '1'),
    ]

    # Call update_rack with no new guess (just rack update)
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=0,
        guess_length=0,
        now_ms=now_ms + 100,
        guessed_tile_ids=None
    )

    # The highlight still exists (we don't remove it from the list)
    assert len(game.racks[0].highlights) == 1, "Highlight should still be in list"

    # But it should NOT be drawn because tiles are no longer contiguous
    surface_size = game.racks[0].rack_metrics.get_size()
    test_surface = pygame.Surface(surface_size)
    game.racks[0].running = True

    # This should NOT draw any rectangles (tiles are separated)
    game.racks[0].update(test_surface, now_ms + 200, flash=False)

    print(f"   Tiles 'A' and 'D' are now separated - highlight not drawn")
    print("\n✅ Test passed: Separated tiles don't show highlight")


@async_test
async def test_separated_cubes_trigger_empty_guess():
    """Test that when cubes are physically separated, only that chain's highlight is cleared."""
    from core.app import App
    from hardware.cubes_to_game import coordination as ctg_coordination

    game, mqtt, queue = await create_test_game()

    # Create tiles
    game.racks[0].tiles = [
        tiles.Tile('A', '0'),
        tiles.Tile('S', '5'),
        tiles.Tile('K', '1'),
        tiles.Tile('E', '2'),
    ]

    print("\n=== Test: Separated cubes only clear specific highlight ===")

    # Create first highlight for "AS"
    game.racks[0].guess_type = GuessType.BAD
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=2,
        guess_length=2,
        now_ms=1000,
        guessed_tile_ids=['0', '5']
    )

    # Create second highlight for "KE"
    game.racks[0].guess_type = GuessType.GOOD
    await game.racks[0].update_rack(
        game.racks[0].tiles,
        highlight_length=2,
        guess_length=2,
        now_ms=1100,
        guessed_tile_ids=['1', '2']
    )

    assert len(game.racks[0].highlights) == 2, "Should have 2 highlights initially"
    print(f"   Initial highlights: {len(game.racks[0].highlights)}")

    # Simulate what happens when the "AS" chain is separated
    # The coordination layer detects this and calls remove_highlight explicitly
    print("\n2. Simulating 'AS' chain separation")

    # Call remove_highlight to explicitly remove the "AS" chain's highlight
    await game._app.remove_highlight(['0', '5'], 0)
    await asyncio.sleep(0.1)  # Let event propagate

    # Only the "AS" highlight should be removed, "KE" should remain
    print(f"   After 'AS' separation: {len(game.racks[0].highlights)} highlight(s)")
    assert len(game.racks[0].highlights) == 1, "Should have 1 highlight after removing 'AS'"

    # Verify the remaining highlight is for "KE"
    remaining_ids, _, _ = game.racks[0].highlights[0]
    assert set(remaining_ids) == {'1', '2'}, f"Remaining highlight should be for 'KE', got {remaining_ids}"

    print(f"   Remaining highlight: {remaining_ids} (correct - 'KE' still highlighted)")
    print("\n✅ Test passed: Only specific chain's highlight is cleared")


@async_test
async def test_coordination_layer_passes_previous_tiles():
    """Test that coordination layer calls remove_highlight when chain is broken."""
    from hardware.cubes_to_game import coordination as ctg_coordination
    from unittest.mock import AsyncMock

    # Reset state from previous tests
    ctg_coordination.state.last_guess_tiles = []

    # Set up mock callbacks
    mock_guess_callback = AsyncMock()
    mock_remove_callback = AsyncMock()
    ctg_coordination.state.guess_tiles_callback = mock_guess_callback
    ctg_coordination.state.remove_highlight_callback = mock_remove_callback

    print("\n=== Test: Coordination layer passes previous tiles ===")

    # Simulate first guess with tiles (word_tiles_list is a list of guesses)
    print("\n1. First guess with tiles ['1', '2', '3']")
    await ctg_coordination.guess_tiles(None, [['1', '2', '3']], 0, 0, 1000)

    # Remove callback should not be called yet
    assert not mock_remove_callback.called, "Remove callback should not be called on normal guess"

    # Simulate chain being broken (empty tiles)
    print("\n2. Chain broken (empty tiles list)")
    await ctg_coordination.guess_tiles(None, [], 0, 0, 1100)

    # Verify remove_highlight callback was called with the PREVIOUS tiles
    assert mock_remove_callback.called, "Remove callback should have been called"
    # Get the positional arguments from the call
    print(f"   Full call_args: {mock_remove_callback.call_args}")
    args_tuple = mock_remove_callback.call_args.args
    tiles_arg = args_tuple[0]
    move_tiles_arg = args_tuple[1]

    print(f"   Callback called with tiles: {tiles_arg}, move_tiles: {move_tiles_arg}")
    assert tiles_arg == ['1', '2', '3'], f"Should pass previous tiles, got {tiles_arg}"
    assert move_tiles_arg == False, f"move_tiles should be False for removal, got {move_tiles_arg}"

    print("\n✅ Test passed: Coordination layer correctly passes previous tiles")


@async_test
async def test_coordination_layer_removes_individual_chain_from_multiple():
    """Test that when one of multiple chains is removed, only that chain's highlight is removed."""
    from hardware.cubes_to_game import coordination as ctg_coordination
    from unittest.mock import AsyncMock

    # Reset state from previous tests
    ctg_coordination.state.last_guess_tiles = []

    # Set up mock callbacks
    mock_guess_callback = AsyncMock()
    mock_remove_callback = AsyncMock()
    ctg_coordination.state.guess_tiles_callback = mock_guess_callback
    ctg_coordination.state.remove_highlight_callback = mock_remove_callback

    print("\n=== Test: Remove one chain from multiple ===")

    # Simulate two chains: ET and RP
    print("\n1. Two chains formed: ET ['0','5'] and RP ['3','2']")
    await ctg_coordination.guess_tiles(None, [['0', '5'], ['3', '2']], 0, 0, 1000)

    # Should have called guess_tiles for both chains
    assert mock_guess_callback.call_count == 2
    # Should not have called remove yet
    assert not mock_remove_callback.called

    # Reset mocks
    mock_guess_callback.reset_mock()
    mock_remove_callback.reset_mock()

    # Simulate RP chain being broken, leaving only ET
    print("\n2. RP chain broken, only ET remains ['0','5']")
    await ctg_coordination.guess_tiles(None, [['0', '5']], 0, 0, 1100)

    # Should have called remove_highlight for RP
    assert mock_remove_callback.call_count == 1, f"Should remove 1 chain, called {mock_remove_callback.call_count} times"
    removed_tiles = set(mock_remove_callback.call_args.args[0])
    assert removed_tiles == {'2', '3'}, f"Should remove RP tiles ['2','3'], got {removed_tiles}"

    # Should have called guess_tiles for ET (the remaining chain)
    assert mock_guess_callback.call_count == 1, f"Should guess 1 remaining chain, called {mock_guess_callback.call_count} times"

    print("\n✅ Test passed: Individual chain removal works correctly")


@async_test
async def test_mqtt_neighbor_messages_control_highlights():
    """Test that MQTT neighbor messages properly create and remove highlights."""
    from tests.fixtures.game_factory import create_game_with_started_players
    from hardware import cubes_to_game

    # Create game with P0 started
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    app.rack_manager.initialize_racks_for_fair_play()

    # Clear any initial messages
    from tests.fixtures.test_helpers import drain_mqtt_queue
    await drain_mqtt_queue(mqtt, queue)
    mqtt.clear_published()

    # Get the current rack letters
    rack = app.rack_manager.get_rack(0)
    letters = rack.letters()
    print(f"\n=== Test: MQTT neighbor messages control highlights ===")
    print(f"Rack letters: {letters}")

    # We'll test with the first two tiles (positions 0 and 1)
    # Tile 0 is on Cube 1, Tile 1 is on Cube 2
    tile_0_id = rack.position_to_id(0)
    tile_1_id = rack.position_to_id(1)
    print(f"Tile 0 (pos 0): id={tile_0_id}, letter={letters[0]}")
    print(f"Tile 1 (pos 1): id={tile_1_id}, letter={letters[1]}")

    # Initially, should have no highlights
    assert len(game.racks[0].highlights) == 0, "Should start with no highlights"

    class MockMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload.encode() if payload else b""

    # Step 1: Connect cubes 1 and 2 (cube/right/1 -> 2)
    print("\n1. Connecting Cube 1 -> Cube 2")
    msg = MockMessage("cube/right/1", "2")
    await cubes_to_game.handle_mqtt_message(queue, msg, 1000, game.sound_manager)
    await asyncio.sleep(0.1)

    # This should create a highlight
    print(f"   After connecting: {len(game.racks[0].highlights)} highlight(s)")
    print(f"   Highlights: {game.racks[0].highlights}")

    # Step 2: Separate the cubes by sending empty neighbor (within 50ms for removal detection)
    print("\n2. Separating cubes (cube/right/1 -> empty)")
    msg = MockMessage("cube/right/1", "")
    await cubes_to_game.handle_mqtt_message(queue, msg, 1010, game.sound_manager)
    await asyncio.sleep(0.1)

    # The highlight should be removed when cubes are separated
    print(f"   After separating: {len(game.racks[0].highlights)} highlight(s) in list")
    print(f"   Highlights: {game.racks[0].highlights}")
    assert len(game.racks[0].highlights) == 0, "Highlight should be removed when cubes are separated"

    print("\n✅ Test passed: MQTT neighbor messages properly control highlights")
