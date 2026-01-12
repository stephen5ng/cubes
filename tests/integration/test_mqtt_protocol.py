
import pytest
import asyncio
from typing import List, Tuple
from tests.fixtures.game_factory import create_game_with_started_players, async_test
from config import game_config
from core import tiles
from tests.fixtures.test_helpers import drain_mqtt_queue

@async_test
async def test_neighbor_report_processing():
    """Verify that neighbor reports from cubes trigger game logic (word formation)."""
    # 1. Setup game with P0 started
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    app.rack_manager.initialize_racks_for_fair_play()
    
    await drain_mqtt_queue(mqtt, queue)
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
    
    await drain_mqtt_queue(mqtt, queue)
    msgs = mqtt.get_published("cube/")
    # Look for border update on Cube 1 or Cube 2
    # "cube/1/border"
    border_msgs = [m for m in msgs if "/border" in m[0]]
    assert len(border_msgs) > 0

from tests.fixtures.test_context import IntegrationTestContext

@async_test
async def test_good_guess_feedback():
    """Verify good guess triggers green border and flash."""
    ctx = await IntegrationTestContext.create(players=[0])
    
    # We can't use ctx.make_guess for this specific test because the original test uses 
    # app.hardware.good_guess() directly, which bypasses some of the logic in App.guess_tiles()
    # that make_guess() wraps. However, the Goal of the test is to verify FEEDBACK.
    # IntegrationTestContext is designed for high-level interactions. 
    # If we want to test LOW LEVEL hardware methods, we might not use Context OR we adapt Context.
    
    # Actually, looking at the Plan, the example REPLACES the low level call with ctx.make_guess.
    # "ctx.make_guess(["0", "1"], player=0)"
    
    # But wait, make_guess invokes `game._app.guess_tiles` which does logic THEN calls hardware.good_guess.
    # The original test manually invoked hardware.good_guess.
    # If we switch to ctx.make_guess, we are testing the FULL stack (App -> Hardware).
    # This is BETTER integration testing.
    # BUT we need to ensure the RACK has the tiles if we use the full stack.
    # The original test didn't care about rack content because it called hardware method directly.
    # To use ctx.make_guess, we need to ensure tiles "0" and "1" are valid/on rack?
    # Context creates game with started players.
    # We might need to setup the rack?
    
    # Let's try to follow the plan's exact code first.
    # The plan assumes we can just call it.
    # Let's verify what make_guess does: `await self.game._app.guess_tiles(tile_ids...)`
    # App.guess_tiles: checks dictionary, if good -> hardware.good_guess.
    # So if we pass random tiles "0", "1", they format a word.
    # Tile 0 is "A", Tile 1 is "B"?
    # If "AB" is not in dictionary, it will trigger bad_guess, not good_guess.
    # The original test FORCED good_guess.
    # The new test assumes "0", "1" form a valid word OR relies on dictionary stubbing?
    # `create_test_game` stubs dictionary with ["TESTING", "EXAMPLE"...].
    # WE PROBABLY NEED TO SETUP THE RACK/DICTIONARY if we go through full stack.
    
    # The Refactoring Plan Example showed:
    # ctx.make_guess(["0", "1"]...)
    # But it didn't show prep.
    
    # I will adapt the test to be ROBUST using the Context.
    # I'll setup the dictionary/rack internally or stick to the hardware call if I want to strictly test hardware.
    # But `IntegrationTestContext` suggests testing the integration.
    
    # Let's check `test_word_validation.py` for how to setup a rack.
    # It sets tiles.
    
    # Minimal approach:
    # 1. Create context.
    # 2. Setup "AB" as valid word.
    # 3. Setup Rack with "A", "B".
    # 4. make_guess(["0", "1"]).
    
    # Actually, if I look at `test_mqtt_protocol.py`, `test_good_guess_feedback` was testing `low level hardware response`.
    # Using `IntegrationTestContext` (which uses `app.guess_tiles`) changes the scope to `full app flow`.
    # This is acceptable and desired ("Refactored tests are shorter and more readable").
    
    # I will stick to the plan but add the necessary setup to make it work (valid word).
    
    ctx = await IntegrationTestContext.create(players=[0])
    
    # Setup: Ensure we have a valid word to guess.
    # Let's use "HI" (2 letters).
    from core.dictionary import Dictionary
    test_dict = Dictionary.from_words(["HI"], min_letters=2, max_letters=6)
    from tests.fixtures.test_helpers import update_app_dictionary
    update_app_dictionary(ctx.game._app, test_dict)
    
    # Setup Rack
    rack = ctx.game._app.rack_manager.get_rack(0)
    tiles = rack.get_tiles()
    tiles[0].letter = "H"
    tiles[1].letter = "I"
    rack.set_tiles(tiles)
    
    # Make guess using Context
    # IDs of first two tiles
    tile_ids = [tiles[0].id, tiles[1].id]
    
    result = await ctx.make_guess(tile_ids, player=0)
    
    ctx.assert_border_color("0x07E0")  # Green
    ctx.assert_flash_sent(cube_id=1) # Provided tiles are usually on cubes 1, 2...
    # Actually tile distribution is random or fixed? 
    # In `create_game_with_started_players` -> `create_test_game`. 
    # Tile 0 is on Cube 1?
    # `rack.get_tiles()`: Cube 1 has tile at header? 
    # Usually yes.
    assert result.flash_sent

@async_test
async def test_bad_old_guess_feedback():
    """Verify bad (white) and old (yellow) guess feedback."""
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    # No direct state import needed
    
    await drain_mqtt_queue(mqtt, queue)
    mqtt.clear_published()
    
    tiles_in_guess = ["0", "1"]
    
    # 1. Bad Guess (White)
    await app.hardware.bad_guess(queue, tiles_in_guess, 0, 0)
    await app.hardware.guess_last_tiles(queue, 0, 0, 2000)
    
    await asyncio.sleep(0.1)
    await drain_mqtt_queue(mqtt, queue)
    
    c1_msgs = mqtt.get_published("cube/1/border")
    assert len(c1_msgs) > 0
    # 0xFFFF is White
    assert "0xFFFF" in c1_msgs[-1][1]
    
    # Verify internal state via App seam
    assert app.get_player_border_color(0) == "0xFFFF"
    
    print(f"DEBUG: Manager border color after bad: {app.get_player_border_color(0)}")
    
    # 2. Old Guess (Yellow)
    mqtt.clear_published()
    
    # Replace callback with no-op to prevent App from overwriting the color
    async def no_op_callback(*args):
        pass
    app.hardware.set_guess_tiles_callback(no_op_callback)
    
    await app.hardware.old_guess(queue, tiles_in_guess, 0, 0)
    
    print(f"DEBUG: Manager border color after old: {app.get_player_border_color(0)}")
    assert app.get_player_border_color(0) == "0xFFE0"
    
    # We also need to set last_guess_tiles because calling guess_last_tiles uses it
    # And currently it might be whatever was last used.
    # But checking state.cube_set_managers[0].border_color is enough to verify old_guess worked.
    # To verify MESSAGE, we call guess_last_tiles.
    # We must ensure last_guess_tiles has our tiles.
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
    await drain_mqtt_queue(mqtt, queue)
    
    c1_msgs = mqtt.get_published("cube/1/border")
    # 0xFFE0 is Yellow
    print(f"DEBUG: Old guess msgs: {c1_msgs}")
    assert "0xFFE0" in c1_msgs[-1][1]
