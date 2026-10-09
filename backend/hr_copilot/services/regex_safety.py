"""Linear-time helpers for matching ordered phrases in user-supplied text."""

import re
from bisect import bisect_left


def has_ordered_regex_matches(text, start_pattern, end_pattern, flags=re.IGNORECASE):
    """Return whether a start match precedes an end match on one line.

    This preserves the meaning of ``start.*end`` while avoiding repeated
    backtracking when user input contains many start phrases and no end phrase.
    Like a regular expression dot, matches do not cross newline characters.
    """
    start_regex = re.compile(start_pattern, flags)
    end_regex = re.compile(end_pattern, flags)

    for line in str(text).split("\n"):
        start_ends = [match.end() for match in start_regex.finditer(line)]
        end_starts = [match.start() for match in end_regex.finditer(line)]
        if start_ends and end_starts and min(start_ends) <= max(end_starts):
            return True
    return False


def find_ordered_capture(text, start_pattern, end_pattern, flags=re.IGNORECASE):
    """Capture text between the first ordered start/end pair in linear time."""
    start_regex = re.compile(start_pattern, flags)
    end_regex = re.compile(end_pattern, flags)

    for line in str(text).split("\n"):
        starts = list(start_regex.finditer(line))
        ends = list(end_regex.finditer(line))
        end_positions = [match.start() for match in ends]
        for start in starts:
            end_index = bisect_left(end_positions, start.end())
            if end_index < len(ends):
                return line[start.end():ends[end_index].start()]
    return None
