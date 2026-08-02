from __future__ import annotations

import re

_TOKEN_EDGE_RE = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)


def clean_rolling_texts(texts: list[str]) -> list[str]:
    """Remove exact rolling-caption repeats while preserving segment boundaries."""
    cleaned: list[str] = []
    previous = ""
    for text in texts:
        current = collapse_adjacent_repeats(text)
        if previous and current:
            current = remove_leading_overlap(previous, current)
        current = " ".join(current.split()).strip()
        cleaned.append(current)
        if current:
            previous = current
    return cleaned


def collapse_adjacent_repeats(
    text: str,
    min_words: int = 3,
    max_words: int = 40,
) -> str:
    """Collapse adjacent repeated word blocks common in rolling ASR captions."""
    tokens = text.split()
    if len(tokens) < min_words * 2:
        return " ".join(tokens)

    for _ in range(8):
        normalized = [_normalize_token(token) for token in tokens]
        output: list[str] = []
        index = 0
        changed = False

        while index < len(tokens):
            largest = min(max_words, (len(tokens) - index) // 2)
            matched = False
            for block_size in range(largest, min_words - 1, -1):
                block = normalized[index : index + block_size]
                if not block or not all(block):
                    continue

                repeat_count = 1
                while index + (repeat_count + 1) * block_size <= len(tokens):
                    start = index + repeat_count * block_size
                    end = start + block_size
                    if normalized[start:end] != block:
                        break
                    repeat_count += 1

                if repeat_count < 2:
                    continue

                output.extend(tokens[index : index + block_size])
                index += repeat_count * block_size
                changed = True
                matched = True
                break

            if not matched:
                output.append(tokens[index])
                index += 1

        tokens = output
        if not changed:
            break

    return " ".join(tokens)


def remove_leading_overlap(
    previous: str,
    current: str,
    min_words: int = 3,
    max_words: int = 60,
) -> str:
    """Remove a repeated suffix/prefix overlap between consecutive cues."""
    previous_tokens = previous.split()
    current_tokens = current.split()
    previous_normalized = [_normalize_token(token) for token in previous_tokens]
    current_normalized = [_normalize_token(token) for token in current_tokens]
    largest = min(max_words, len(previous_tokens), len(current_tokens))

    for overlap_size in range(largest, min_words - 1, -1):
        if previous_normalized[-overlap_size:] == current_normalized[:overlap_size]:
            return " ".join(current_tokens[overlap_size:])
    return current


def _normalize_token(token: str) -> str:
    return _TOKEN_EDGE_RE.sub("", token).casefold()
