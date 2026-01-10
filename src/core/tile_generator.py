import random
import logging
from collections import Counter
from core.anagram_helper import AnagramHelper
from config import game_config

class TileGenerator:
    """
    Centralized service for generating tiles and managing RNG state.
    This ensures a Single Source of Truth for randomness, decoupled from Rack instances.
    """
    def __init__(self):
        self._anagram_helper = AnagramHelper.get_instance()
        # Shared RNG state logic could go here if we needed to persist/restore it centrally
        self._random_state = random.getstate()

    def get_next_letter(self, current_letters: str) -> str:
        """
        Generate the next letter based on the current letters (on the board/rack).
        Uses AnagramHelper to find viable candidates that form high-scoring words.
        """
        # Score all candidates (A-Z) by anagram count
        candidates = self._anagram_helper.score_candidates(current_letters)
        logging.debug(f"gen_next_letter: Candidates: " + ", ".join([f"{l}:{s}" for l, s in candidates]))
        
        if not candidates:
            # Fallback if no candidates (shouldn't happen with valid inputs)
            return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        max_score = candidates[0][1]
        
        # Filter to viable candidates (those meeting threshold)
        # Using the constant from tiles.py logic, reused here
        CANDIDATE_THRESHOLD_RATIO = 2.0 / 3.0
        threshold = CANDIDATE_THRESHOLD_RATIO * max_score
        
        viable = [c for c in candidates if c[1] >= threshold]
        logging.debug(f"gen_next_letter: Viable candidates: " + ", ".join([f"{l}:{s}" for l, s in viable]))
        
        # Select randomly from viable candidates
        # We don't need to explicitly set/get state if we assume this is the main sequence,
        # but for safety/testability we could. 
        # For now, just using global random which is what we want to drive.
        
        best_letter, score = random.choice(viable)
        
        logging.debug(f"gen_next_letter: Selected {best_letter} (score {score})")
        return best_letter
