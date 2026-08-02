from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from .models import TranscriptData, TranscriptSegment

_TRANSCRIPT_ENDPOINT = "https://youtube-transcript.ai/transcript/{video_id}.txt"
_INVIDIOUS_REGISTRY = "https://api.invidious.io/instances.json"
_TIMESTAMP_RE = re.compile(
    r"^\[(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})\]\s*(?P<text>.+)$"
)
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_USER_AGENT = "AITubeTranscript/0.1 (+https://github.com/organicoverlords/AITubeTranscript)"


class FrontendError(RuntimeError):
    pass


def fetch_transcript_proxy(
    video_id: str,
    languages: tuple[str, ...],
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    for language in languages or ("en",):
        query = urlencode({"lang": language})
        url = f"{_TRANSCRIPT_ENDPOINT.format(video_id=video_id)}?{query}"
        source = f"youtube-transcript.ai:{language}"
        try:
            body = _fetch_text(url, timeout=25)
            transcript = parse_transcript_markdown(body, source, language)
            attempts.append(
                {
                    "source": source,
                    "ok": bool(transcript.segments),
                    "segment_count": len(transcript.segments),
                }
            )
            if transcript.segments:
                return transcript
        except Exception as exc:
            attempts.append({"source": source, "ok": False, "error": str(exc)})
    return None


def parse_transcript_markdown(
    body: str,
    source: str,
    language_code: str | None,
) -> TranscriptData:
    cleaned = body.lstrip("\ufeff").strip()
    if not cleaned or cleaned.lower().startswith(("<!doctype", "<html")):
        raise FrontendError("Transcript endpoint returned an empty or HTML response")
    lowered = cleaned.lower()
    if any(
        marker in lowered
        for marker in (
            "transcript unavailable",
            "no transcript",
            "video unavailable",
            "rate limit exceeded",
            "too many requests",
        )
    ):
        raise FrontendError("Transcript endpoint reported that no transcript was available")

    timed: list[tuple[float, str]] = []
    untimed: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _TIMESTAMP_RE.match(line)
        if match:
            hours = int(match.group("hours") or 0)
            minutes = int(match.group("minutes"))
            seconds = int(match.group("seconds"))
            start = float(hours * 3600 + minutes * 60 + seconds)
            text = match.group("text").strip()
            if text:
                timed.append((start, text))
            continue
        if line.startswith("#") or _looks_like_metadata(line):
            continue
        untimed.append(line)

    segments: list[TranscriptSegment] = []
    for index, (start, text) in enumerate(timed):
        next_start = timed[index + 1][0] if index + 1 < len(timed) else start
        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                duration=max(0.0, next_start - start),
            )
        )
    if not segments:
        text = "\n".join(untimed).strip()
        if len(text) >= 20:
            segments.append(TranscriptSegment(text=text, start=0.0, duration=0.0))

    return TranscriptData(
        source=source,
        language=None,
        language_code=language_code,
        is_generated=None,
        segments=segments,
    )


def fetch_oembed(
    canonical_url: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    endpoint = "https://www.youtube.com/oembed?" + urlencode(
        {"url": canonical_url, "format": "json"}
    )
    try:
        payload = _fetch_json(endpoint, timeout=15)
        attempts.append({"source": "youtube oEmbed", "ok": True})
        return {
            "title": payload.get("title"),
            "uploader": payload.get("author_name"),
            "channel_url": payload.get("author_url"),
            "thumbnail": payload.get("thumbnail_url"),
        }
    except Exception as exc:
        attempts.append({"source": "youtube oEmbed", "ok": False, "error": str(exc)})
        return {}


def fetch_invidious_data(
    video_id: str,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        registry = _fetch_json(_INVIDIOUS_REGISTRY, timeout=15)
    except Exception as exc:
        attempts.append({"source": "Invidious registry", "ok": False, "error": str(exc)})
        return {}, []

    instances = _eligible_invidious_instances(registry)
    attempts.append(
        {"source": "Invidious registry", "ok": bool(instances), "instance_count": len(instances)}
    )
    metadata: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []
    for base_uri in instances[:6]:
        if not metadata:
            metadata = _fetch_invidious_video(base_uri, video_id, attempts)
        if comment_limit > 0 and not comments:
            comments = _fetch_invidious_comments(
                base_uri,
                video_id,
                comment_limit,
                attempts,
            )
        if metadata and (comments or comment_limit <= 0):
            break
    return metadata, comments


def _fetch_invidious_video(
    base_uri: str,
    video_id: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    source = f"Invidious video:{urlparse(base_uri).hostname}"
    try:
        payload = _fetch_json(f"{base_uri}/api/v1/videos/{video_id}", timeout=15)
        attempts.append({"source": source, "ok": True})
        return {
            "id": video_id,
            "title": payload.get("title"),
            "description": payload.get("description"),
            "channel": payload.get("author"),
            "channel_id": payload.get("authorId"),
            "channel_url": payload.get("authorUrl"),
            "duration": payload.get("lengthSeconds"),
            "view_count": payload.get("viewCount"),
            "like_count": payload.get("likeCount"),
            "comment_count": payload.get("commentCount"),
            "published": payload.get("published"),
            "thumbnail": _best_thumbnail(payload.get("videoThumbnails")),
        }
    except Exception as exc:
        attempts.append({"source": source, "ok": False, "error": str(exc)})
        return {}


def _fetch_invidious_comments(
    base_uri: str,
    video_id: str,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source = f"Invidious comments:{urlparse(base_uri).hostname}"
    endpoint = f"{base_uri}/api/v1/comments/{video_id}?" + urlencode({"sort_by": "top"})
    try:
        payload = _fetch_json(endpoint, timeout=20)
        raw_comments = payload.get("comments") or []
        comments = [
            {
                "author": item.get("author"),
                "text": item.get("content") or item.get("contentHtml"),
                "like_count": item.get("likeCount"),
                "timestamp": item.get("published"),
                "parent": None,
            }
            for item in raw_comments[: max(0, comment_limit)]
        ]
        attempts.append({"source": source, "ok": bool(comments), "count": len(comments)})
        return comments
    except Exception as exc:
        attempts.append({"source": source, "ok": False, "error": str(exc)})
        return []


def _eligible_invidious_instances(registry: Any) -> list[str]:
    if not isinstance(registry, list):
        return []
    instances: list[str] = []
    for item in registry:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[1], dict):
            continue
        details = item[1]
        monitor = details.get("monitor") or {}
        if details.get("api") is not True or details.get("type") != "https":
            continue
        if monitor.get("down") is True:
            continue
        uri = str(details.get("uri") or "").rstrip("/")
        if _is_safe_public_https_uri(uri):
            instances.append(uri)
    return instances


def _is_safe_public_https_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _fetch_json(url: str, timeout: int) -> Any:
    return json.loads(_fetch_text(url, timeout=timeout))


def _fetch_text(url: str, timeout: int) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise FrontendError("Only HTTPS frontend URLs are allowed")
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed/validated hosts
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise FrontendError("Frontend response exceeded the 5 MiB safety limit")
    return payload.decode("utf-8", errors="replace")


def _looks_like_metadata(line: str) -> bool:
    lowered = line.lower()
    prefixes = (
        "title:",
        "source:",
        "language:",
        "duration:",
        "word count:",
        "available languages:",
        "video id:",
        "url:",
    )
    return lowered.startswith(prefixes)


def _best_thumbnail(value: Any) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    candidates = [item for item in value if isinstance(item, dict) and item.get("url")]
    if not candidates:
        return None
    return str(max(candidates, key=lambda item: int(item.get("width") or 0))["url"])
