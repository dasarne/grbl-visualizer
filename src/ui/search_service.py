"""Pure search/replace helpers for editor text operations."""

from __future__ import annotations

import re

TextRange = tuple[int, int]


def compute_match_ranges(
    term: str,
    use_regex: bool,
    content: str,
    ranges: list[TextRange],
    case_sensitive: bool = False,
) -> list[TextRange]:
    """Return all match ranges within the given text ranges."""
    if not term:
        return []

    results: list[TextRange] = []

    if use_regex:
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        try:
            pattern = re.compile(term, flags)
        except re.error:
            return []

        for start_bound, end_bound in ranges:
            target = content[start_bound:end_bound]
            for match in pattern.finditer(target):
                results.append((start_bound + match.start(), start_bound + match.end()))
        return results

    for start_bound, end_bound in ranges:
        target = content[start_bound:end_bound]
        search_target = target if case_sensitive else target.lower()
        search_term = term if case_sensitive else term.lower()
        start = 0
        while True:
            index = search_target.find(search_term, start)
            if index == -1:
                break
            begin = start_bound + index
            end = begin + len(term)
            results.append((begin, end))
            start = index + len(term)

    return results


def find_next_match(matches: list[TextRange], anchor: int) -> TextRange | None:
    """Return the next match at/after anchor, wrapping around."""
    if not matches:
        return None
    for start, end in matches:
        if start >= anchor:
            return (start, end)
    return matches[0]


def find_previous_match(matches: list[TextRange], anchor: int) -> TextRange | None:
    """Return the previous match before anchor, wrapping around."""
    if not matches:
        return None
    for start, end in reversed(matches):
        if end <= anchor:
            return (start, end)
    return matches[-1]


def replace_all_in_ranges(
    content: str,
    ranges: list[TextRange],
    needle: str,
    replacement: str,
    use_regex: bool,
    case_sensitive: bool = False,
) -> tuple[str, int]:
    """Replace all matches within ranges and return (new_content, count)."""
    if not needle:
        return (content, 0)

    try:
        new_content = content
        count = 0

        for start_bound, end_bound in reversed(ranges):
            target = new_content[start_bound:end_bound]
            if use_regex:
                flags = re.MULTILINE
                if not case_sensitive:
                    flags |= re.IGNORECASE
                new_target, local_count = re.subn(
                    needle,
                    replacement,
                    target,
                    flags=flags,
                )
            else:
                if case_sensitive:
                    local_count = target.count(needle)
                    new_target = target.replace(needle, replacement)
                else:
                    # Case-insensitive literal replace preserves original case in non-matched parts
                    local_count = target.lower().count(needle.lower())
                    new_target, local_count = _replace_case_insensitive(target, needle, replacement)

            if local_count == 0:
                continue

            count += local_count
            new_content = (
                new_content[:start_bound]
                + new_target
                + new_content[end_bound:]
            )

        return (new_content, count)
    except re.error:
        return (content, 0)


def _replace_case_insensitive(text: str, needle: str, replacement: str) -> tuple[str, int]:
    """Replace all occurrences of needle in text case-insensitively."""
    count = 0
    result: list[str] = []
    lower_text = text.lower()
    lower_needle = needle.lower()
    start = 0
    needle_len = len(needle)
    while True:
        index = lower_text.find(lower_needle, start)
        if index == -1:
            result.append(text[start:])
            break
        result.append(text[start:index])
        result.append(replacement)
        count += 1
        start = index + needle_len
    return "".join(result), count
