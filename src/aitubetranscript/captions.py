from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.request import Request, urlopen

from .models import TranscriptData, TranscriptSegment

_TAG_RE = re.compile(r"<[^>]+>")


def fetch_caption_document(url: str, timeout: int = 30) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 AITubeTranscript/0.1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL comes from yt-dlp
        return response.read()


def parse_json3(payload: bytes, source: str, language_code: str | None) -> TranscriptData:
    document = json.loads(payload.decode("utf-8"))
    segments: list[TranscriptSegment] = []
    for event in document.get("events", []):
        text = "".join(piece.get("utf8", "") for piece in event.get("segs", []))
        text = text.replace("\n", " ").strip()
        if not text:
            continue
        start = float(event.get("tStartMs", 0)) / 1000.0
        duration = float(event.get("dDurationMs", 0)) / 1000.0
        segments.append(TranscriptSegment(text=text, start=start, duration=duration))
    return TranscriptData(
        source=source,
        language=None,
        language_code=language_code,
        is_generated="automatic" in source,
        segments=segments,
    )


def parse_vtt(payload: bytes, source: str, language_code: str | None) -> TranscriptData:
    text = payload.decode("utf-8", errors="replace").replace("\r\n", "\n")
    segments: list[TranscriptSegment] = []
    current_start: float | None = None
    current_end: float | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_end, current_lines
        if current_start is not None and current_end is not None and current_lines:
            raw = " ".join(current_lines)
            clean = html.unescape(_TAG_RE.sub("", raw)).strip()
            if clean and (not segments or segments[-1].text != clean):
                segments.append(
                    TranscriptSegment(
                        text=clean,
                        start=current_start,
                        duration=max(0.0, current_end - current_start),
                    )
                )
        current_start = None
        current_end = None
        current_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if " --> " in stripped:
            flush()
            start_text, end_text = stripped.split(" --> ", 1)
            current_start = _parse_vtt_time(start_text)
            current_end = _parse_vtt_time(end_text.split()[0])
        elif not stripped:
            flush()
        elif current_start is not None and not stripped.startswith(
            ("WEBVTT", "Kind:", "Language:")
        ):
            current_lines.append(stripped)
    flush()

    return TranscriptData(
        source=source,
        language=None,
        language_code=language_code,
        is_generated="automatic" in source,
        segments=segments,
    )


def _parse_vtt_time(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        raise ValueError(f"Invalid VTT timestamp: {value}")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def select_caption_track(
    info: dict[str, Any], languages: list[str]
) -> tuple[str, dict[str, Any], bool] | None:
    for generated, collection_name in ((False, "subtitles"), (True, "automatic_captions")):
        collection = info.get(collection_name) or {}
        for requested in languages:
            candidates = [requested, f"{requested}-orig"]
            candidates.extend(key for key in collection if key.startswith(f"{requested}-"))
            for language_code in dict.fromkeys(candidates):
                formats = collection.get(language_code) or []
                if not formats:
                    continue
                preferred = next((item for item in formats if item.get("ext") == "json3"), None)
                preferred = preferred or next(
                    (item for item in formats if item.get("ext") == "vtt"), None
                )
                preferred = preferred or formats[0]
                return language_code, preferred, generated
    return None
