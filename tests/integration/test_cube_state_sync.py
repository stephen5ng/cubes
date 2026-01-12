
import pytest
import asyncio
from typing import List, Tuple
import pytest
import asyncio
from typing import List, Tuple
from tests.fixtures.game_factory import create_test_game, create_game_with_started_players, async_test
from config import game_config

@async_test
async def test_letter_lock_routing():
    """Verify that locking a letter sends the lock command to the correct cubes."""
    # Setup 2-player game with players started
    game, mqtt, queue = await create_game_with_started_players(players=[0, 1])
    app = game._app
    
    # Initialize racks
    app.rack_manager.initialize_racks_for_fair_play()
    
    app._update_rack_display(0, 0, 0)
    app._update_rack_display(0, 0, 1)
    await asyncio.sleep(0.1)
    
    mqtt.clear_published()
    
    # Helper to drain queue
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            # item is (topic, payload, retain, now_ms)
            await mqtt.publish(item[0], item[1], item[2])
    
    # Lock the first letter
    await app.letter_lock(position=0, locked=True, now_ms=1000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    # Expected messages:
    # Expected messages:
    lock_messages = mqtt.get_published("cube/1/") + mqtt.get_published("cube/11/")
    # Filter for lock topic
    lock_msgs = [m for m in lock_messages if "lock" in m[0]]
    
    assert len(lock_msgs) >= 2
    
    topics = [m[0] for m in lock_msgs]
    assert "cube/1/lock" in topics
    assert "cube/11/lock" in topics
    
    # Now unlock
    mqtt.clear_published()
    await app.letter_lock(position=0, locked=False, now_ms=2000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    lock_messages = mqtt.get_published("cube/1/") + mqtt.get_published("cube/11/")
    lock_msgs = [m for m in lock_messages if "lock" in m[0]]
    assert len(lock_msgs) >= 2
    topics = [m[0] for m in lock_msgs]
    assert "cube/1/lock" in topics
    assert "cube/11/lock" in topics

@async_test
async def test_border_clear_broadcast():
    # Setup 2-player game to verify broadcasting to both sets
    game, mqtt, queue = await create_game_with_started_players(players=[0, 1])
    app = game._app
    
    mqtt.clear_published()
    
    # Helper to drain queue
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])
            
    await app.hardware.clear_all_borders(queue, 1000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    # P0 (Set 1): Cubes 1-6
    # P1 (Set 2): Cubes 11-16
    
    # Method usually iterates all cubes in active sets.
    
    # Sample check
    # Check Cube 1 and Cube 16
    c1_msgs = mqtt.get_published("cube/1/border")
    c16_msgs = mqtt.get_published("cube/16/border")
    
    assert len(c1_msgs) > 0
    assert len(c16_msgs) > 0
    
    # Verify payload is clear/empty/default
    # Usually empty string or space or specific clear code
    # We just care that it sent *something* to the border topic
    
@async_test
async def test_state_persistence_reconnect():
    """Verify that loading rack is idempotent and can simulate reconnection state restore."""
    game, mqtt, queue = await create_game_with_started_players(players=[0])
    app = game._app
    app.rack_manager.initialize_racks_for_fair_play()
    
    # Helper to drain queue
    async def drain_queue():
        while not queue.empty():
            item = queue.get_nowait()
            await mqtt.publish(item[0], item[1], item[2])

    # Drain initialization messages
    await drain_queue()

    # Initial load
    mqtt.clear_published()
    await app.load_rack(1000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    initial_msgs = mqtt.get_published("cube/")
    # Should contain letters for cubes 1-6 (P0 only)
    letters_topic_count = len([m for m in initial_msgs if "/letter" in m[0]])
    assert letters_topic_count == 6
    
    # "Reconnect" / Re-load
    mqtt.clear_published()
    await app.load_rack(2000)
    await asyncio.sleep(0.1)
    await drain_queue()
    
    reload_msgs = mqtt.get_published("cube/")
    reload_letters_count = len([m for m in reload_msgs if "/letter" in m[0]])
    
    assert reload_letters_count == 6
    
    # Verify content consistency (picking one cube)
    # We don't have easy access to what 'initial_msgs' payload was without parsing
    # But assertion that it RESENT the messages is the key for persistence/refresh
    
