
import pytest
import asyncio
from typing import List, Tuple
from tests.fixtures.game_factory import create_game_with_started_players, async_test
from config import game_config
from core import tiles

@async_test
async def test_neighbor_report_processing():
    """Verify that neighbor reports from cubes trigger game logic (word formation)."""
    # 1. Setup game with P0 started
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    app.rack_manager.initialize_racks_for_fair_play()
    
    # Helper to drain queue
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])
    
    await drain_queue()
    mqtt.clear_published()

    # 2. Assign known letters to cubes so we can predict the word
    # Cube 1 -> Tile 0 -> "A" (example)
    # Cube 2 -> Tile 1 -> "B"
    # We need to know what letters are on the rack.
    rack = app.rack_manager.get_rack(0)
    letters = rack.letters()
    
    # Let's force specific letters for deterministic testing
    # Or just use what's there. Max 6 letters.
    # Tile 0 is on Cube 1 (usually). Tile 1 on Cube 2.
    
    # 3. Simulate neighbor report: Cube 1 has right neighbor Cube 2
    # Topic: cube/right/1, Payload: 2
    
    # We need to ensure the App is listening. App init calls cubes_to_game.init(mqtt).
    # FakeMqttClient handles inject_message -> triggers callback?
    # No, FakeMqttClient.inject_message puts it in a queue. App needs a consumer loop?
    # But in coordination.py, handle_mqtt_message is called... BY WHOM?
    # In main.py, there's a listener loop. In tests, we likely don't have that loop running automatically?
    
    # Let's verify if `game_factory` sets up a listener.
    # It does NOT appear to set up a 'handle_mqtt_message' loop in `create_test_game`. 
    # Usually App has a `start` method or similar.
    # We might need to manually call `cubes_to_game.handle_mqtt_message` if the test fixture doesn't run the loop.
    
    # Check `test_neighbor_report_processing` goal: "Verify handling...".
    # If the integration test environment doesn't run the loop, we should invoke the handler directly
    # OR start the loop. Invoking handler directly is safer integration test for logic layer.
    
    from hardware import cubes_to_game
    
    class MockMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload.encode()

    # Simulate Cube 1 -> Cube 2
    msg = MockMessage("cube/right/1", "2")
    
    # Determine what word this form using rack letters
    # Tile 0 -> Cube 1, Tile 1 -> Cube 2
    # Word: letters[0] + letters[1]
    expected_word = letters[0] + letters[1]
    
    # 4. Handle the message
    await cubes_to_game.handle_mqtt_message(queue, msg, 1000, game.sound_manager)
    await asyncio.sleep(0.1)
    
    # 5. Verification:
    # Game should have received a 'guess'.
    # App.guess_tiles sets state.last_guess_tiles.
    # And triggers `guess_last_tiles` -> `guess_tiles_callback` (App.guess_tiles).
    # App.guess_tiles logic: updates score, sends feedback.
    
    # If the word is valid/invalid, we get different feedback.
    # But primarily, we want to see a request to lock/flash/border related to these tiles.
    
    await drain_queue()
    msgs = mqtt.get_published("cube/")
    # Look for border update on Cube 1 or Cube 2
    # "cube/1/border"
    border_msgs = [m for m in msgs if "/border" in m[0]]
    assert len(border_msgs) > 0

@async_test
async def test_good_guess_feedback():
    """Verify good guess triggers green border and flash."""
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])
    await drain_queue()
    mqtt.clear_published()
    
    # Tiles 0 and 1
    tiles_in_guess = ["0", "1"]
    
    # Manually invoke hardware.good_guess
    await app.hardware.good_guess(queue, tiles_in_guess, 0, 0, 1000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    # Check for flash (primary feedback for good guess)
    c1_flash = mqtt.get_published("cube/1/flash")
    assert len(c1_flash) > 0
    
    # Check that internal border color state is Green
    # We need access to the manager state to verify this without triggering a redraw
    from hardware.cubes_to_game import state
    manager = state.cube_set_managers[0]
    assert manager.border_color == "0x07E0" # Green

@async_test
async def test_bad_old_guess_feedback():
    """Verify bad (white) and old (yellow) guess feedback."""
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    from hardware.cubes_to_game import state # Import state for debugging
    
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])
    await drain_queue()
    mqtt.clear_published()
    
    tiles_in_guess = ["0", "1"]
    
    # 1. Bad Guess (White)
    await app.hardware.bad_guess(queue, tiles_in_guess, 0, 0)
    await app.hardware.guess_last_tiles(queue, 0, 0, 2000)
    
    await asyncio.sleep(0.1)
    await drain_queue()
    
    c1_msgs = mqtt.get_published("cube/1/border")
    assert len(c1_msgs) > 0
    # 0xFFFF is White
    assert "0xFFFF" in c1_msgs[-1][1]
    
    print(f"DEBUG: Manager border color after bad: {state.cube_set_managers[0].border_color}")
    
    # 2. Old Guess (Yellow)
    mqtt.clear_published()
    
    # Replace callback with no-op to prevent App from overwriting the color
    async def no_op_callback(*args):
        pass
    app.hardware.set_guess_tiles_callback(no_op_callback)
    
    await app.hardware.old_guess(queue, tiles_in_guess, 0, 0)
    
    print(f"DEBUG: Manager border color after old: {state.cube_set_managers[0].border_color}")
    
    # We also need to set last_guess_tiles because calling guess_last_tiles uses it
    # And currently it might be whatever was last used.
    # But checking state.cube_set_managers[0].border_color is enough to verify old_guess worked.
    # To verify MESSAGE, we call guess_last_tiles.
    # We must ensure last_guess_tiles has our tiles.
    from hardware.cubes_to_game import state
    state.last_guess_tiles = [tiles_in_guess] # wait, it is list of lists? No, list of str?
    # coordination.py: guess_last_tiles iterates: for guess in state.last_guess_tiles:
    # If last_guess_tiles is list of guesses?
    # coordination.py: guess_tiles(..., word_tiles_list, ...) sets state.last_guess_tiles = word_tiles_list
    # In handle_mqtt_message: word_tiles_list is returned by process_neighbor_cube.
    # process_neighbor_cube returns List[str] (list of words).
    # So last_guess_tiles is List[str] (list of words strings? No, tiles?)
    # Wait.
    # coordination.py:
    # async def guess_tiles(..., word_tiles_list, ...):
    #     state.last_guess_tiles = word_tiles_list
    #     await guess_last_tiles(...)
    # async def guess_last_tiles(...):
    #     for guess in state.last_guess_tiles:
    #         await callback(...)
    #     await manager._mark_tiles_for_guess(..., state.last_guess_tiles, ...)
    
    # _mark_tiles_for_guess(..., guess_tiles: List[str], ...)
    # signature: guess_tiles: List[str] ???
    # In CubeSetManager:
    # async def _mark_tiles_for_guess(..., guess_tiles: List[str], ...):
    #     for guess in guess_tiles:
    #         for i, tile in enumerate(guess): ...
    
    # So `guess` is a string (word?) or list of tile IDs?
    # If `guess` is a list of tile IDs, then `guess_tiles` is List[List[str]]?
    # coordination.py says `word_tiles_list`.
    # `process_neighbor_cube` returns `self._form_words_from_chain()`.
    # `_form_words_from_chain` returns `List[str]`. Each string is tile IDs concatenated?
    # "01".
    # _mark_tiles_for_guess iterates `guess_tiles`. `guess` is "01".
    # enumerate(guess): '0', '1'.
    
    # So `last_guess_tiles` is `List[str]`. The strings are tile IDs concatenated.
    # Correct.
    
    state.last_guess_tiles = ["".join(tiles_in_guess)]
    
    await app.hardware.guess_last_tiles(queue, 0, 0, 3000)
    
    await asyncio.sleep(0.1)
    await drain_queue()
    
    c1_msgs = mqtt.get_published("cube/1/border")
    # 0xFFE0 is Yellow
    print(f"DEBUG: Old guess msgs: {c1_msgs}")
    assert "0xFFE0" in c1_msgs[-1][1]
