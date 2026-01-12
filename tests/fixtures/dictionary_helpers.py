"""Test helpers for dictionary creation and management."""
from typing import List
from core.dictionary import Dictionary


def create_test_dictionary(words: List[str], **kwargs) -> Dictionary:
    """Create a minimal test dictionary.

    Args:
        words: List of valid words
        **kwargs: Additional arguments for Dictionary.from_words

    Returns:
        Dictionary instance ready for testing
    """
    return Dictionary.from_words(words, **kwargs)


# Common test dictionaries
MINIMAL_DICT = ["CAT", "DOG", "BIRD"]
SCORING_DICT = ["CAT", "FOUR", "FIVES", "SIXLET"]  # 3, 4, 5, 6 letter words
VALIDATION_DICT = ["HELLO", "WORLD", "TEST"]
