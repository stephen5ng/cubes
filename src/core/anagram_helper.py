import os
import string
from itertools import combinations
import logging
from config import game_config

logger = logging.getLogger(__name__)

# Word length constraints for anagram index
MIN_WORD_LENGTH = 3
MAX_WORD_LENGTH = 6

class AnagramHelper:
    _instance = None
    _freq_map = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AnagramHelper()
        return cls._instance

    def __init__(self):
        self._build_index()

    def _build_index(self):
        if self._freq_map is not None:
            return
            
        self._freq_map = {}
        dict_path = game_config.DICTIONARY_PATH        
        if not os.path.exists(dict_path):
             raise FileNotFoundError(f"Dictionary not found at {dict_path}")

        count = 0
        with open(dict_path, "r") as f:
            for line in f:
                word = line.strip().lower()
                if MIN_WORD_LENGTH <= len(word) <= MAX_WORD_LENGTH and word.isalpha():
                    sig = self._compute_signature(word)
                    self._freq_map[sig] = self._freq_map.get(sig, 0) + 1
                    count += 1
        
        logger.info(f"Built in-memory anagram index with {len(self._freq_map)} signatures from {count} words")

    def _compute_signature(self, letters_iter):
        """
        Compute frequency signature from an iterable of characters.
        """
        freq = [0] * 26
        for c in letters_iter:
            idx = ord(c) - ord('a')
            if 0 <= idx < 26:
                freq[idx] += 1
        return tuple(freq)

    def count_anagrams(self, letters):
        """
        Count total number of anagrams (valid words) that can be formed 
        using a subset of the provided letters.
        """
        if not self._freq_map:
            return 0
            
        total = 0
        letters = letters.lower()
        seen_signatures = set()
        
        for size in range(MIN_WORD_LENGTH, len(letters) + 1):
            for combo in combinations(letters, size):
                # combo is a tuple of characters, e.g. ('a', 'b', 'c')
                # Compute signature directly avoiding Counter overhead
                sig = self._compute_signature(combo)
                
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    total += self._freq_map.get(sig, 0)

        return total

    def score_candidates(self, base_letters):
        """
        Calculate anagram counts for all possible next letters (A-Z).
        Returns a list of (letter, score) tuples, sorted by score descending.
        """
        candidates = []
        for char in string.ascii_uppercase:
            score = self.count_anagrams(base_letters + char)
            candidates.append((char, score))
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
