"""Linear-time helpers for matching ordered phrases in user-supplied text."""

import re
from bisect import bisect_left

_EMAIL_LOCAL_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789._%+-"
)
_EMAIL_DOMAIN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789.-"
)
_EMAIL_REGEX_CASE_SPECIALS = frozenset("İı")


def _matches_email_character(character, allowed):
    """Mirror Python's case-insensitive ASCII character classes."""
    return (
        character.casefold() in allowed
        or character in _EMAIL_REGEX_CASE_SPECIALS
    )


def find_email_address(text):
    """Find the first email-shaped token without regex backtracking.

    This accepts the same basic ASCII address shape used by the Copilot's
    identity extractors: a local token, ``@``, a dotted domain, and a TLD of
    at least two letters. Each input character is scanned a bounded number of
    times, including malformed long addresses.
    """
    if not isinstance(text, str):
        return None

    index = 0
    length = len(text)
    while index < length:
        if not _matches_email_character(text[index], _EMAIL_LOCAL_CHARS):
            index += 1
            continue

        local_start = index
        while (
            index < length
            and _matches_email_character(text[index], _EMAIL_LOCAL_CHARS)
        ):
            index += 1
        if index >= length or text[index] != "@":
            continue

        domain_start = index + 1
        domain_end = domain_start
        while (
            domain_end < length
            and _matches_email_character(
                text[domain_end], _EMAIL_DOMAIN_CHARS
            )
        ):
            domain_end += 1

        last_tld_end = None
        dot_index = domain_start
        while dot_index < domain_end:
            if (
                text[dot_index] == "."
                and dot_index + 2 < domain_end
                and text[dot_index + 1].isalpha()
                and text[dot_index + 2].isalpha()
            ):
                tld_end = dot_index + 1
                while tld_end < domain_end and text[tld_end].isalpha():
                    tld_end += 1
                last_tld_end = tld_end
            dot_index += 1

        if last_tld_end is not None:
            return text[local_start:last_tld_end]

    return None


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
