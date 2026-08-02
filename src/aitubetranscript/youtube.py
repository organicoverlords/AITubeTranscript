from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class InvalidYouTubeURL(ValueError):
    pass


def extract_video_id(value: str) -> str:
    candidate = value.strip()
    if _VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise InvalidYouTubeURL("Only youtube.com and youtu.be URLs are accepted")

    video_id: str | None = None
    if host.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            video_id = parts[1]

    if not video_id or not _VIDEO_ID_RE.fullmatch(video_id):
        raise InvalidYouTubeURL("Could not extract a valid 11-character YouTube video ID")
    return video_id


def canonical_url(video_id: str) -> str:
    if not _VIDEO_ID_RE.fullmatch(video_id):
        raise InvalidYouTubeURL("Invalid YouTube video ID")
    return f"https://www.youtube.com/watch?v={video_id}"
