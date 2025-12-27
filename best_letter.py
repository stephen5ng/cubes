#!/usr/bin/env python3
import sys
import os
import pickle
import string
from collections import defaultdict
from itertools import combinations

CACHE_FILE = "word_index.pkl"

def build_word_index(dict_path):
    """
    Build a map from sorted-letter-key -> number of words with that exact multiset.
    Only includes words of length 3..6 and alphabetic.
    """
    idx = defaultdict(int)
    with open(dict_path, 'r', encoding='utf-8') as f:
        for line in f:
            w = line.strip().lower()
            if 3 <= len(w) <= 6 and w.isalpha():
                key = ''.join(sorted(w))
                idx[key] += 1
    return idx

def load_word_index():
    """Load or build the word index."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    else:
        if not os.path.exists("sowpods.txt"):
            print("Error: words.txt not found.", file=sys.stderr)
            sys.exit(1)
        idx = build_word_index("sowpods.txt")
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(idx, f)
        return idx

def count_words_for_rack_tuple(rack_tuple, word_index, cache):
    """
    rack_tuple: tuple of 6 letters (lowercase)
    word_index: map sorted-key -> count
    cache: dict for memoizing results per sorted-rack-key (multiset)
    Returns count of words (3..6 letters) that can be formed from this rack.
    """
    cache_key = tuple(sorted(rack_tuple))
    if cache_key in cache:
        return cache[cache_key]

    total = 0
    n = len(rack_tuple)  # should be 6
    for k in range(3, n+1):
        for comb in combinations(range(n), k):
            subset = [rack_tuple[i] for i in comb]
            key = ''.join(sorted(subset))
            total += word_index.get(key, 0)
    cache[cache_key] = total
    return total

def rank_replacement_letters(rack, word_index):
    """
    rack: string of 6 letters (e.g. "acdeef")
    word_index: prebuilt index
    Returns a dict mapping letter -> expected number of words.
    """
    rack = rack.lower()
    assert len(rack) == 6 and rack.isalpha(), "Input must be exactly 6 letters"
    rack_list = list(rack)
    cache = {}
    scores = {}
    for x in string.ascii_lowercase:
        s = 0
        for i in range(6):
            modified = list(rack_list)
            modified[i] = x
            s += count_words_for_rack_tuple(tuple(modified), word_index, cache)
        expected = s / 6.0
        scores[x] = expected
    return scores

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: {} RACK [N]".format(sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    rack = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) == 3 else 5

    word_index = load_word_index()
    scores = rank_replacement_letters(rack, word_index)

    # Sort by score (descending), then alphabetically
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))

    print(f"Top {N} replacement letters for rack '{rack}':")
    for ch, val in ranked[:N]:
        print(f"  {ch}: {int(val)} expected words")

if __name__ == "__main__":
    main()
