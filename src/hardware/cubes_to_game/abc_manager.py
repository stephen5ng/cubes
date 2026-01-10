"""ABC sequence and countdown management for game start.

This module manages the ABC countdown sequence that players use to start a game.
"""

import logging
from typing import List

from . import state


def _find_non_touching_cubes_for_player(manager) -> List[str]:
    """Find 3 non-touching cubes for a specific player."""
    available_cubes = [cube for cube in manager.cube_list if cube in manager.cubes_to_neighbors]

    if len(available_cubes) < 3:
        return available_cubes  # Return what we have, even if less than 3
    logging.debug(f"manager cube chain: {manager.cube_chain}")
    selected_cubes = []
    for cube in available_cubes:
        if len(selected_cubes) >= 3:
            break
        logging.debug(f"checking cube {cube}")
        # Check if this cube touches any already selected cube
        is_touching = any(
            manager.cube_chain.get(cube) == selected or
            manager.cube_chain.get(selected) == cube
            for selected in selected_cubes
        )

        if not is_touching:
            selected_cubes.append(cube)

    logging.debug(f"selected: {selected_cubes}")
    return selected_cubes[:3]


class ABCManager:
    """Manages ABC sequence and countdown logic."""

    def __init__(self):
        # ABC sequence state
        self.abc_start_active = False
        self.player_abc_cubes = {}  # Maps player number to their ABC cube assignments

        # Countdown state
        self.player_countdown_active = {}  # Track which players are in countdown phase
        self.global_countdown_schedule = []  # List of (time, replacement_type)
        self.countdown_complete_time = None  # When the global countdown will complete

    def reset(self):
        """Reset all ABC/countdown state."""
        self.abc_start_active = False
        self.player_abc_cubes = {}
        self.player_countdown_active = {}
        self.global_countdown_schedule = []
        self.countdown_complete_time = None

    def is_any_player_in_countdown(self) -> bool:
        """Check if any player is currently in countdown phase."""
        return bool(self.player_countdown_active)

    async def assign_abc_letters_to_available_players(self, publish_queue, now_ms: int, cube_set_managers: list) -> None:
        """Assign ABC letters to players who have enough cubes but don't have ABC assignments yet.

        Args:
            publish_queue: Queue for MQTT messages
            now_ms: Current timestamp
            cube_set_managers: List of CubeSetManager instances
        """
        self.abc_start_active = True
        letters = ["A", "B", "C"]
        for manager in cube_set_managers:
            # Skip if this player already has ABC assignments
            if manager.cube_set_id in self.player_abc_cubes:
                continue

            player_abc_cubes = _find_non_touching_cubes_for_player(manager)
            if len(player_abc_cubes) >= 3:
                self.player_abc_cubes[manager.cube_set_id] = {
                    "A": player_abc_cubes[0],
                    "B": player_abc_cubes[1],
                    "C": player_abc_cubes[2]
                }
                for i, letter in enumerate(letters):
                    cube_id = player_abc_cubes[i]
                    # Publish letter using queue
                    await publish_queue.put((f"cube/{cube_id}/letter", letter, True, now_ms))
                    logging.info(f"activating abc: {cube_id}: {letter}")

    async def activate_abc_start_sequence(self, publish_queue, now_ms: int, cube_set_managers: list) -> None:
        """Activate the ABC sequence start system.

        Args:
            publish_queue: Queue for MQTT messages
            now_ms: Current timestamp
            cube_set_managers: List of CubeSetManager instances
        """
        # Check if any player has at least 3 cubes with neighbor reports
        has_enough_cubes = False
        for manager in cube_set_managers:
            available_cubes = [cube for cube in manager.cube_list if cube in manager.cubes_to_neighbors]
            if len(available_cubes) >= 3:
                has_enough_cubes = True
                break

        if not has_enough_cubes:
            return  # Wait until at least one player has enough cubes

        await self.assign_abc_letters_to_available_players(publish_queue, now_ms, cube_set_managers)

    async def check_abc_sequence_complete(self, cube_set_managers: list):
        """Check if A-B-C cubes are placed in sequence.

        Args:
            cube_set_managers: List of CubeSetManager instances

        Returns:
            Player number if complete, None otherwise
        """
        if not self.abc_start_active:
            return None
        # Check all cube managers for ABC sequence using the stored assignments
        for manager in cube_set_managers:
            logging.debug(f"checking abc sequence: {manager.cube_set_id}: {self.player_abc_cubes} {self.player_countdown_active} ")
            player_num = manager.cube_set_id
            if (player_num in self.player_abc_cubes and
                    player_num not in self.player_countdown_active):
                # Get the specific cubes that were assigned ABC for this player
                player_abc = self.player_abc_cubes[player_num]
                cube_a = player_abc["A"]
                cube_b = player_abc["B"]
                cube_c = player_abc["C"]

                logging.info(f"ABC check: manager {player_num} checking {cube_a}->{cube_b}->{cube_c} in chain={manager.cube_chain}")

                # Check if A->B->C chain exists for this player's assigned ABC cubes
                if (cube_a in manager.cube_chain and
                        manager.cube_chain[cube_a] == cube_b and
                        cube_b in manager.cube_chain and
                        manager.cube_chain[cube_b] == cube_c):
                    logging.info(f"ABC sequence complete for player {player_num}!")
                    return player_num

        return None

    async def execute_letter_stage_for_player(self, publish_queue, player: int, stage_type: str, now_ms: int,
                                               sound_manager, cube_set_managers: list) -> None:
        """Execute a letter stage for a specific player.

        Args:
            publish_queue: Queue for MQTT messages
            player: Player number
            stage_type: Type of stage ('non_abc_1', 'A', 'B', 'C', etc.)
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
        """
        abc_cubes = self.player_abc_cubes[player]
        all_player_cubes = cube_set_managers[player].cube_list
        abc_cube_ids = set(abc_cubes.values())
        non_abc_cubes = [cube for cube in all_player_cubes if cube not in abc_cube_ids]

        cube_id = None
        if stage_type == 'non_abc_1':
            cube_id = non_abc_cubes[0]
        elif stage_type == 'non_abc_2':
            cube_id = non_abc_cubes[1]
        elif stage_type == 'non_abc_3':
            cube_id = non_abc_cubes[2]
        elif stage_type == 'A':
            cube_id = abc_cubes['A']
        elif stage_type == 'B':
            cube_id = abc_cubes['B']
        elif stage_type == 'C':
            cube_id = abc_cubes['C']

        if cube_id:
            await publish_queue.put((f"cube/{cube_id}/letter", "?", True, now_ms))
            sound_manager.play_chunk()

    async def apply_past_letter_stages(self, publish_queue, player: int, now_ms: int, sound_manager,
                                        cube_set_managers: list) -> None:
        """Apply letter stages that have already occurred for a player joining mid-countdown.

        Args:
            publish_queue: Queue for MQTT messages
            player: Player number
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
        """
        # Apply all stages that should have already happened
        for stage_time, stage_type in self.global_countdown_schedule:
            if stage_time < now_ms:  # This stage is in the past
                await self.execute_letter_stage_for_player(publish_queue, player, stage_type, now_ms, sound_manager,
                                                            cube_set_managers)

    async def execute_countdown_stage(self, publish_queue, stage_type: str, now_ms: int, sound_manager,
                                       cube_set_managers: list) -> None:
        """Execute a countdown stage for all active countdown players.

        Args:
            publish_queue: Queue for MQTT messages
            stage_type: Type of stage to execute
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
        """
        for player in self.player_countdown_active:
            await self.execute_letter_stage_for_player(publish_queue, player, stage_type, now_ms, sound_manager,
                                                        cube_set_managers)

    async def sync_player_with_countdown(self, publish_queue, player: int, now_ms: int, sound_manager,
                                          cube_set_managers: list) -> None:
        """Sync a player's cubes with the existing countdown animation.

        This function makes the second player's cubes change to '?' in sync with
        the global letter-by-letter countdown progression.

        Args:
            publish_queue: Queue for MQTT messages
            player: Player number
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
        """
        self.player_countdown_active[player] = True

        logging.info(f"Player {player} joining countdown - will sync with global letter progression")

        await self.apply_past_letter_stages(publish_queue, player, now_ms, sound_manager, cube_set_managers)

    async def start_abc_countdown(self, publish_queue, player: int, now_ms: int, abc_countdown_delay_ms: int) -> None:
        """Start the global ABC countdown sequence.

        Args:
            publish_queue: Queue for MQTT messages
            player: Player number who triggered the countdown
            now_ms: Current timestamp
            abc_countdown_delay_ms: Delay between countdown stages
        """
        delay_ms = abc_countdown_delay_ms
        self.player_countdown_active[player] = True

        logging.info(f"ABC sequence complete for player {player}! Starting global countdown")

        # Create global countdown schedule: 3 non-ABC stages, then A, B, C (500ms intervals)
        stages = ['non_abc_1', 'non_abc_2', 'non_abc_3', 'A', 'B', 'C']
        self.global_countdown_schedule = [(now_ms + i * delay_ms, stage) for i, stage in enumerate(stages)]

        # Game will start after the last replacement
        self.countdown_complete_time = now_ms + len(stages) * delay_ms

    async def handle_abc_completion(self, publish_queue, completed_player: int, now_ms: int, sound_manager,
                                     cube_set_managers: list, abc_countdown_delay_ms: int) -> None:
        """Handle when a player completes their ABC sequence.

        If someone is already in countdown, join them. Otherwise start a new countdown.

        Args:
            publish_queue: Queue for MQTT messages
            completed_player: Player who completed ABC
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
            abc_countdown_delay_ms: Delay between countdown stages
        """
        # Play ping sound when ABC cubes are connected
        sound_manager.play_crash()
        if self.is_any_player_in_countdown():
            logging.info(f"Player {completed_player} joining active countdown")
            await self.sync_player_with_countdown(publish_queue, completed_player, now_ms, sound_manager,
                                                   cube_set_managers)
        else:
            logging.info(f"Player {completed_player} starting new countdown")
            await self.start_abc_countdown(publish_queue, completed_player, now_ms, abc_countdown_delay_ms)

    async def check_countdown_completion(self, publish_queue, now_ms: int, sound_manager, cube_set_managers: list,
                                          start_game_callback) -> list:
        """Check if countdown stages need to be executed and if countdown has completed.

        Args:
            publish_queue: Queue for MQTT messages
            now_ms: Current timestamp
            sound_manager: SoundManager instance
            cube_set_managers: List of CubeSetManager instances
            start_game_callback: Callback to start the game

        Returns:
            List of incidents for any countdown replacements that occurred
        """
        incidents = []

        # Execute any pending global countdown stages
        if self.global_countdown_schedule:
            remaining_stages = []
            for stage_time, stage_type in self.global_countdown_schedule:
                if now_ms >= stage_time:
                    # Execute this stage for all active countdown players
                    await self.execute_countdown_stage(publish_queue, stage_type, now_ms, sound_manager,
                                                        cube_set_managers)
                    incidents.append(f"abc_countdown_replacement: {stage_type}")
                else:
                    remaining_stages.append((stage_time, stage_type))
            self.global_countdown_schedule = remaining_stages

        # Check for completed countdowns
        completed_players = []
        if self.countdown_complete_time is not None and now_ms >= self.countdown_complete_time:
            sound_manager.play_crash()
            # All players in countdown complete at the same time
            for player in list(self.player_countdown_active.keys()):
                logging.info(f"ABC countdown complete for player {player}! Starting game at {now_ms}")

                state.add_started_cube_set(player)
                completed_players.append(player)

                await start_game_callback(True, self.countdown_complete_time, player)
            self.reset()

        # If any player completed countdown, clean up countdown state
        if completed_players:
            # Clear global countdown state
            self.global_countdown_schedule = []
            self.countdown_complete_time = None

        return incidents
