#!/usr/bin/env python3
"""
Non-Retained MQTT Architecture

Strategies for reducing retained message usage while maintaining 
game state consistency and cube synchronization.
"""

import asyncio
import time
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from enum import Enum

class MessageStrategy(Enum):
    """Different strategies for handling state without retained messages"""
    IMMEDIATE_ONLY = "immediate"      # Send only when changed, no retention
    PERIODIC_SYNC = "periodic"        # Periodic full state broadcast
    ON_DEMAND_SYNC = "on_demand"      # Send state when cube requests it
    HYBRID = "hybrid"                 # Mix of strategies per message type

@dataclass
class CubeState:
    """Track cube state locally instead of relying on MQTT retained messages"""
    cube_id: str
    letter: str = " "
    border_top: Optional[str] = None
    border_bottom: Optional[str] = None 
    border_left: Optional[str] = None
    border_right: Optional[str] = None
    locked: bool = False
    last_updated: float = field(default_factory=time.time)
    
    def needs_sync(self, max_age_seconds: float = 30.0) -> bool:
        """Check if state is old enough to need re-sync"""
        return time.time() - self.last_updated > max_age_seconds

class NonRetainedMqttManager:
    """Manages MQTT communication without retained messages"""
    
    def __init__(self, publish_queue: asyncio.Queue):
        self.publish_queue = publish_queue
        self.cube_states: Dict[str, CubeState] = {}
        self.strategy = MessageStrategy.HYBRID
        self.sync_interval_s = 10.0  # Periodic sync every 10 seconds
        self.last_full_sync = 0.0
        self.cube_online_status: Dict[str, float] = {}  # Track when cubes were last seen
        
    async def set_cube_letter(self, cube_id: str, letter: str, now_ms: int, force_send: bool = False):
        """Set cube letter using non-retained strategy"""
        
        # Update local state
        if cube_id not in self.cube_states:
            self.cube_states[cube_id] = CubeState(cube_id)
        
        current_state = self.cube_states[cube_id]
        
        # Only send if changed or forced
        if current_state.letter != letter or force_send:
            current_state.letter = letter
            current_state.last_updated = now_ms / 1000
            
            # Send non-retained message
            await self.publish_queue.put((f"cube/{cube_id}/letter", letter, False, now_ms))
            logging.info(f"Sent non-retained letter {letter} to cube {cube_id}")
    
    async def set_cube_border(self, cube_id: str, border_type: str, color: Optional[str], now_ms: int, force_send: bool = False):
        """Set cube border using non-retained strategy"""
        
        if cube_id not in self.cube_states:
            self.cube_states[cube_id] = CubeState(cube_id)
        
        current_state = self.cube_states[cube_id]
        current_value = getattr(current_state, f"border_{border_type}", None)
        
        # Only send if changed or forced
        if current_value != color or force_send:
            setattr(current_state, f"border_{border_type}", color)
            current_state.last_updated = now_ms / 1000
            
            # Send non-retained message
            await self.publish_queue.put((f"cube/{cube_id}/border_{border_type}", color, False, now_ms))
            logging.info(f"Sent non-retained border {border_type}={color} to cube {cube_id}")

    async def set_cube_borders_consolidated(self, cube_id: str, border_directions: dict, now_ms: int, force_send: bool = False):
        """Set cube borders using consolidated messaging (much more efficient)
        
        Args:
            cube_id: Target cube ID
            border_directions: Dict like {"N": "0xFF0000", "S": "0xFF0000", "E": None, "W": None}
                              None/missing means clear that border
            now_ms: Timestamp
            force_send: Force send even if unchanged
        """
        
        if cube_id not in self.cube_states:
            self.cube_states[cube_id] = CubeState(cube_id)
        
        current_state = self.cube_states[cube_id]
        
        # Build the consolidated message
        directions_with_color = []
        color = None
        
        # Map N/S/E/W to border_type names for state tracking
        direction_to_type = {"N": "top", "S": "bottom", "E": "right", "W": "left"}
        
        # Find the active color and directions
        for direction, dir_color in border_directions.items():
            if dir_color:  # Non-None, non-empty
                if color is None:
                    color = dir_color
                elif color != dir_color:
                    raise ValueError("All borders must have the same color in consolidated protocol")
                directions_with_color.append(direction)
        
        # Check if this represents a change in border state
        changed = force_send
        if not changed:
            for direction, dir_color in border_directions.items():
                border_type = direction_to_type[direction]
                current_value = getattr(current_state, f"border_{border_type}", None)
                if current_value != dir_color:
                    changed = True
                    break
        
        if changed:
            # Update state
            for direction, dir_color in border_directions.items():
                border_type = direction_to_type[direction]
                setattr(current_state, f"border_{border_type}", dir_color)
            current_state.last_updated = now_ms / 1000
            
            # Build message: "NSW:0xFF0000" or ":"
            if directions_with_color and color:
                message = f"{''.join(sorted(directions_with_color))}:{color}"
            else:
                message = ":"  # Clear all borders
            
            # Send consolidated message  
            await self.publish_queue.put((f"cube/{cube_id}/border", message, False, now_ms))
            logging.info(f"Sent consolidated border {message} to cube {cube_id}")
    
    async def set_cube_lock(self, cube_id: str, locked: bool, now_ms: int, force_send: bool = False):
        """Set cube lock status using non-retained strategy"""
        
        if cube_id not in self.cube_states:
            self.cube_states[cube_id] = CubeState(cube_id)
        
        current_state = self.cube_states[cube_id]
        
        # Only send if changed or forced
        if current_state.locked != locked or force_send:
            current_state.locked = locked
            current_state.last_updated = now_ms / 1000
            
            # Send non-retained message
            lock_value = "1" if locked else None
            await self.publish_queue.put((f"cube/{cube_id}/lock", lock_value, False, now_ms))
            logging.info(f"Sent non-retained lock {locked} to cube {cube_id}")
    
    async def handle_cube_sync_request(self, cube_id: str, now_ms: int):
        """Handle a cube requesting full state sync"""
        if cube_id in self.cube_states:
            state = self.cube_states[cube_id]
            
            # Send current state with force_send=True
            await self.set_cube_letter(cube_id, state.letter, now_ms, force_send=True)
            await self.set_cube_lock(cube_id, state.locked, now_ms, force_send=True)
            
            # Send all border states
            for border_type in ["top", "bottom", "left", "right"]:
                color = getattr(state, f"border_{border_type}", None)
                await self.set_cube_border(cube_id, border_type, color, now_ms, force_send=True)
            
            logging.info(f"Sent full state sync to cube {cube_id}")
    
    async def periodic_sync_task(self):
        """Periodically sync state to all cubes"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval_s)
                
                now_ms = time.time() * 1000
                cubes_needing_sync = []
                
                # Find cubes that haven't been updated recently
                for cube_id, state in self.cube_states.items():
                    if state.needs_sync():
                        cubes_needing_sync.append(cube_id)
                
                if cubes_needing_sync:
                    logging.info(f"Periodic sync for {len(cubes_needing_sync)} cubes")
                    
                    for cube_id in cubes_needing_sync:
                        await self.handle_cube_sync_request(cube_id, now_ms)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Periodic sync error: {e}")
    
    def mark_cube_online(self, cube_id: str, now_ms: int):
        """Mark that a cube is online based on receiving a message from it"""
        self.cube_online_status[cube_id] = now_ms / 1000
    
    def get_offline_cubes(self, timeout_s: float = 60.0) -> Set[str]:
        """Get cubes that haven't been seen recently"""
        now = time.time()
        offline_cubes = set()
        
        for cube_id, last_seen in self.cube_online_status.items():
            if now - last_seen > timeout_s:
                offline_cubes.add(cube_id)
        
        return offline_cubes
    
    async def start_services(self):
        """Start background services for non-retained messaging"""
        sync_task = asyncio.create_task(self.periodic_sync_task(), name="periodic_sync")
        return [sync_task]
    
    def get_strategy_stats(self) -> Dict:
        """Get statistics about the non-retained strategy performance"""
        now = time.time()
        
        states_by_age = {
            "fresh": 0,      # < 10s old
            "stale": 0,      # 10-30s old  
            "old": 0         # > 30s old
        }
        
        for state in self.cube_states.values():
            age = now - state.last_updated
            if age < 10:
                states_by_age["fresh"] += 1
            elif age < 30:
                states_by_age["stale"] += 1
            else:
                states_by_age["old"] += 1
        
        offline_cubes = self.get_offline_cubes()
        
        return {
            "strategy": self.strategy.value,
            "total_cubes": len(self.cube_states),
            "state_freshness": states_by_age,
            "offline_cubes": len(offline_cubes),
            "sync_interval_s": self.sync_interval_s,
            "last_full_sync_ago_s": now - self.last_full_sync
        }

# Migration helpers

async def migrate_to_non_retained(publish_queue: asyncio.Queue, cube_managers, topic_patterns: Dict[str, bool]):
    """
    Gradually migrate specific topics to non-retained messaging.
    
    topic_patterns: Dict mapping topic patterns to whether they should be non-retained
    e.g. {"cube/*/letter": True, "cube/*/border_*": False} 
    """
    
    non_retained_manager = NonRetainedMqttManager(publish_queue)
    
    # Override the publish queue to intercept and modify retain flags
    original_put = publish_queue.put
    
    async def modified_put(item):
        topic, message, retain, timestamp = item
        
        # Check if this topic should be non-retained
        should_be_non_retained = False
        for pattern, non_retained in topic_patterns.items():
            if pattern_matches(topic, pattern):
                should_be_non_retained = non_retained
                break
        
        if should_be_non_retained:
            # Convert to non-retained
            modified_item = (topic, message, False, timestamp)
            await original_put(modified_item)
        else:
            # Keep original retain flag
            await original_put(item)
    
    publish_queue.put = modified_put
    return non_retained_manager

def pattern_matches(topic: str, pattern: str) -> bool:
    """Simple pattern matching for MQTT topics (supports * wildcard)"""
    import re
    # Convert MQTT pattern to regex
    regex_pattern = pattern.replace("*", "[^/]+").replace("#", ".*")
    return re.match(f"^{regex_pattern}$", topic) is not None

# Configuration presets for different migration strategies

MIGRATION_STRATEGIES = {
    "conservative": {
        # Only flash messages (already non-retained)
        "cube/*/flash": True
    },
    
    "moderate": {
        # Flash and NFC messages
        "cube/*/flash": True,
        "game/nfc/*": True
    },
    
    "aggressive": {
        # Everything except letters (most critical for state)
        "cube/*/flash": True,
        "game/nfc/*": True,
        "cube/*/border_*": True,
        "cube/*/lock": True
    },
    
    "full": {
        # All messages non-retained
        "cube/*": True,
        "game/*": True
    }
}