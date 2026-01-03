"""Test analyzer for generating human-readable summaries of functional tests."""

import json
from pathlib import Path
from typing import Dict, List, Tuple


class GameEvent:
    """Represents a parsed game event."""
    def __init__(self, time_ms: int, event_type: str, data: dict):
        self.time_ms = time_ms
        self.time_s = time_ms / 1000.0
        self.event_type = event_type
        self.data = data


class TestSummary:
    """Generates human-readable summaries from test output."""

    def __init__(self, output_file: str):
        self.output_file = output_file
        self.events: List[GameEvent] = []
        self.words_by_player: Dict[int, List[Tuple[str, int]]] = {}
        self.scores_by_player: Dict[int, int] = {}
        self.letter_moves = 0
        self.duration_s = 0.0

    def parse(self):
        """Parse the output JSONL file and extract events."""
        if not Path(self.output_file).exists():
            raise FileNotFoundError(f"Output file not found: {self.output_file}")

        with open(self.output_file, 'r') as f:
            for line in f:
                if line.strip():
                    event_data = json.loads(line)
                    time_ms = event_data.get('time', 0)
                    event_type = event_data.get('event_type', 'unknown')

                    event = GameEvent(time_ms, event_type, event_data)
                    self.events.append(event)

                    # Track specific event types
                    if event_type == 'word_formed':
                        player = event_data.get('player', 0)
                        word = event_data.get('word', '')
                        score = event_data.get('score', 0)

                        if player not in self.words_by_player:
                            self.words_by_player[player] = []
                            self.scores_by_player[player] = 0

                        self.words_by_player[player].append((word, score))
                        self.scores_by_player[player] += score

                    elif event_type == 'letter_position':
                        self.letter_moves += 1

        # Calculate duration from last event
        if self.events:
            self.duration_s = self.events[-1].time_s

    def generate_summary(self, test_name: str = "Test") -> str:
        """Generate a human-readable summary of the test."""
        lines = []
        lines.append(f"Test: {test_name}")
        lines.append(f"Duration: {self.duration_s:.1f}s")
        lines.append("")

        if not self.events:
            lines.append("No events recorded")
            return "\n".join(lines)

        # Timeline of key events
        lines.append("Timeline:")

        # Group events to avoid spam from letter_position
        prev_event_type = None
        letter_move_count = 0
        last_letter_time = 0

        for event in self.events:
            if event.event_type == 'letter_position':
                if prev_event_type != 'letter_position':
                    letter_move_count = 0
                letter_move_count += 1
                last_letter_time = event.time_s
                prev_event_type = 'letter_position'
                continue
            else:
                # Flush accumulated letter moves
                if letter_move_count > 0 and prev_event_type == 'letter_position':
                    if letter_move_count == 1:
                        lines.append(f"{last_letter_time:5.1f}s - Letter moved")
                    else:
                        lines.append(f"{last_letter_time:5.1f}s - Letter moved ({letter_move_count} moves)")
                    letter_move_count = 0

                prev_event_type = event.event_type

            if event.event_type == 'word_formed':
                word = event.data.get('word', '')
                player = event.data.get('player', 0)
                score = event.data.get('score', 0)
                lines.append(f"{event.time_s:5.1f}s - Player {player} scored \"{word}\" ({score} points)")

        # Flush any remaining letter moves
        if letter_move_count > 0:
            if letter_move_count == 1:
                lines.append(f"{last_letter_time:5.1f}s - Letter moved")
            else:
                lines.append(f"{last_letter_time:5.1f}s - Letter moved ({letter_move_count} moves)")

        lines.append("")

        # Summary statistics
        if self.words_by_player:
            lines.append("Final Scores:")
            for player in sorted(self.scores_by_player.keys()):
                score = self.scores_by_player[player]
                word_count = len(self.words_by_player[player])
                lines.append(f"  Player {player}: {score} points ({word_count} words)")

        if self.letter_moves > 0:
            lines.append(f"\nLetter Moves: {self.letter_moves}")

        return "\n".join(lines)

    def get_statistics(self) -> Dict:
        """Get test statistics as a dictionary."""
        return {
            'duration_s': self.duration_s,
            'total_events': len(self.events),
            'letter_moves': self.letter_moves,
            'players': {
                player: {
                    'score': self.scores_by_player.get(player, 0),
                    'words': len(self.words_by_player.get(player, [])),
                    'word_list': [w[0] for w in self.words_by_player.get(player, [])]
                }
                for player in self.scores_by_player.keys()
            }
        }


def analyze_test(output_file: str, test_name: str = None) -> str:
    """Analyze a test output file and return a human-readable summary.

    Args:
        output_file: Path to output.jsonl file
        test_name: Optional test name for the summary header

    Returns:
        Human-readable summary string
    """
    if test_name is None:
        test_name = Path(output_file).parent.name if 'goldens' in output_file else "Test"

    summary = TestSummary(output_file)
    summary.parse()
    return summary.generate_summary(test_name)


class SemanticDiff:
    """Compares two test outputs semantically, not byte-by-byte."""

    def __init__(self, golden_file: str, actual_file: str, time_tolerance_ms: int = 100):
        self.golden_file = golden_file
        self.actual_file = actual_file
        self.time_tolerance_ms = time_tolerance_ms

        self.golden_summary = TestSummary(golden_file)
        self.actual_summary = TestSummary(actual_file)

        self.golden_summary.parse()
        self.actual_summary.parse()

        self.differences = []

    def compare(self) -> bool:
        """Compare the two outputs semantically.

        Returns:
            True if outputs match semantically, False otherwise
        """
        self.differences = []

        # Compare word formations
        self._compare_words()

        # Compare scores
        self._compare_scores()

        # Compare event counts (with tolerance)
        self._compare_event_counts()

        return len(self.differences) == 0

    def _compare_words(self):
        """Compare word formations between golden and actual."""
        golden_players = set(self.golden_summary.words_by_player.keys())
        actual_players = set(self.actual_summary.words_by_player.keys())

        # Check for player mismatches
        if golden_players != actual_players:
            self.differences.append(
                f"Player mismatch - Expected players: {sorted(golden_players)}, "
                f"Actual players: {sorted(actual_players)}"
            )
            return

        # Compare words for each player
        for player in golden_players:
            golden_words = self.golden_summary.words_by_player[player]
            actual_words = self.actual_summary.words_by_player[player]

            # Convert to sets of (word, score) for comparison
            golden_set = set(golden_words)
            actual_set = set(actual_words)

            missing = golden_set - actual_set
            extra = actual_set - golden_set

            if missing:
                for word, score in sorted(missing):
                    self.differences.append(
                        f"Player {player}: Missing word \"{word}\" ({score} points)"
                    )

            if extra:
                for word, score in sorted(extra):
                    self.differences.append(
                        f"Player {player}: Extra word \"{word}\" ({score} points) not in golden"
                    )

    def _compare_scores(self):
        """Compare final scores between golden and actual."""
        for player in self.golden_summary.scores_by_player.keys():
            golden_score = self.golden_summary.scores_by_player.get(player, 0)
            actual_score = self.actual_summary.scores_by_player.get(player, 0)

            if golden_score != actual_score:
                self.differences.append(
                    f"Player {player}: Score mismatch - Expected: {golden_score}, "
                    f"Actual: {actual_score}"
                )

    def _compare_event_counts(self):
        """Compare event counts with tolerance for minor variations."""
        golden_moves = self.golden_summary.letter_moves
        actual_moves = self.actual_summary.letter_moves

        # Allow small variations in letter moves (rendering timing differences)
        move_diff = abs(golden_moves - actual_moves)
        if move_diff > 5:  # More than 5 move difference is significant
            self.differences.append(
                f"Letter move count differs significantly - Expected: {golden_moves}, "
                f"Actual: {actual_moves} (diff: {move_diff})"
            )

    def get_diff_report(self, test_name: str = "Test") -> str:
        """Generate a human-readable diff report.

        Args:
            test_name: Name of the test for the report header

        Returns:
            Human-readable diff report string
        """
        if not self.differences:
            return f"Test: {test_name}\n✓ Outputs match semantically"

        lines = []
        lines.append(f"Test: {test_name}")
        lines.append("="*70)
        lines.append("SEMANTIC DIFFERENCES")
        lines.append("="*70)
        lines.append("")

        for diff in self.differences:
            lines.append(f"  • {diff}")

        lines.append("")
        lines.append(f"Total differences: {len(self.differences)}")

        return "\n".join(lines)


def compare_tests_semantically(golden_file: str, actual_file: str, test_name: str = None) -> tuple[bool, str]:
    """Compare two test outputs semantically and return match status and report.

    Args:
        golden_file: Path to golden output.jsonl file
        actual_file: Path to actual output.jsonl file
        test_name: Optional test name for the report header

    Returns:
        Tuple of (matches: bool, report: str)
    """
    if test_name is None:
        test_name = Path(golden_file).parent.name if 'goldens' in golden_file else "Test"

    diff = SemanticDiff(golden_file, actual_file)
    matches = diff.compare()
    report = diff.get_diff_report(test_name)

    return matches, report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_analyzer.py <output.jsonl> [test_name]")
        print("       python test_analyzer.py --diff <golden.jsonl> <actual.jsonl> [test_name]")
        sys.exit(1)

    if sys.argv[1] == "--diff":
        if len(sys.argv) < 4:
            print("Usage: python test_analyzer.py --diff <golden.jsonl> <actual.jsonl> [test_name]")
            sys.exit(1)

        golden_file = sys.argv[2]
        actual_file = sys.argv[3]
        test_name = sys.argv[4] if len(sys.argv) > 4 else None

        matches, report = compare_tests_semantically(golden_file, actual_file, test_name)
        print(report)
        sys.exit(0 if matches else 1)
    else:
        output_file = sys.argv[1]
        test_name = sys.argv[2] if len(sys.argv) > 2 else None

        print(analyze_test(output_file, test_name))
