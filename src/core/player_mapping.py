from typing import Dict, List

def calculate_player_mapping(started_cube_sets: List[int]) -> Dict[int, int]:
    """
    Determines which Logical Player ID maps to which Physical Cube Set ID.
    
    Rules:
    - No sets (Keyboard mode): Identity mapping for default players (0,1 -> 0,1) or just Player 0 depending on usage.
      Wait, existing logic was: if not started_sets, use default mapping BUT only mark Player 0 as started.
      The App logic uses `_player_to_cube_set = {0: 0, 1: 1}` by default in `__init__`.
      In `_set_player_to_cube_set_mapping`, if not started:
         `self._hardware.add_player_started(0)`
         AND it returns early, leaving `_player_to_cube_set` as whatever it was instantiated with (0:0, 1:1) or potentially empty if we cleared it?
      
      Looking at `App.py` lines 89-93 (original):
      ```python
        if not started_cube_sets:
            # No cube sets started via ABC (keyboard start), use default mapping
            # Mark player 0 as started with cube set 0
            self._hardware.add_player_started(0)
            return
      ```
      The mapping `self._player_to_cube_set` is initialized to `{0:0, 1:1}` in `__init__`.
      So the function should probably return the "Active" mapping.
      But `App` uses the mapping to look up `cube_set_id`.
      If Player 0 is started, `App` looks up `_player_to_cube_set[0]`.
      So `calculate_player_mapping` should return the mapping that *Active* players will use.
      
      Let's replicate behavior: 
      If no hardware started -> Return full default mapping {0:0, 1:1} (since P0 might play, and maybe P1 via keyboard? Usually only P0 starts).
      Actually, strict equivalence:
      Rule:
      If [] -> Return {0:0, 1:1} (but caller only activates P0).
      If [1] -> Return {1:1} (Caller activates P1).
      If [0] -> Return {0:0} (Caller activates P0).
      If [0, 1] -> Return {0:0, 1:1} (Caller activates P0, P1).
    """
    if not started_cube_sets:
        # Default/Keyboard mode: Logic implies P0 plays on "virtual" set 0.
        # Original code didn't touch _player_to_cube_set if not started_sets, so it stayed {0:0, 1:1}.
        return {0: 0, 1: 1}

    if len(started_cube_sets) == 1:
        # Single player: use cube set ID as player ID to preserve which physical set was used
        sid = started_cube_sets[0]
        return {sid: sid}

    # Multi-player: map players sequentially to their cube sets
    # e.g. Sets [5, 2] -> Sorted [2, 5] -> Player 0: Set 2, Player 1: Set 5
    sorted_sets = sorted(started_cube_sets)
    return {i: sid for i, sid in enumerate(sorted_sets)}
