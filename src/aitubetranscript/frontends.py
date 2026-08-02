from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .models import TranscriptData, TranscriptSegment

_TRANSCRIPT_ENDPOINT = "https://youtube-transcript.ai/transcript/{video_id}.txt"
_YOUTUBE2TEXT_BASE = "https://youtube2text.org"
_INVIDIOUS_REGISTRY = "https://api.invidious.io/instances.json"
_TRUSTED_INVIDIOUS = (
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yt.chocolatemoo53.com",
)
_TIMESTAMP_RE = re.compile(
    r"^\[(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})\]\s*(?P<text>.+)$"
)
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_USER_AGENT = "AITubeTranscript/0.2 (+https://github.com/organicoverlords/AITubeTranscript)"


class FrontendError(RuntimeError):
    pass


def fetch_transcript_proxy(
    video_id: str,
    languages: tuple[str, ...],
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    transcript = _fetch_youtube_transcript_ai(video_id, languages, attempts)
    if transcript is not None:
        return transcript
    return _fetch_youtube2text(video_id, attempts)


def _fetch_youtube_transcript_ai(
    video_id: str,
    languages: tuple[str, ...],
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    choices = tuple(dict.fromkeys((*languages, ""))) or ("",)
    for language in choices:
        query = f"?{urlencode({'lang': language})}" if language else ""
        url = f"{_TRANSCRIPT_ENDPOINT.format(video_id=video_id)}{query}"
        source = f"youtube-transcript.ai:{language or 'default'}"
        try:
            body = _fetch_text(url, timeout=25)
            transcript = parse_transcript_markdown(body, source, language or None)
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


def _fetch_youtube2text(
    video_id: str,
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    source = "youtube2text.org"
    try:
        key_response = _fetch_json(f"{_YOUTUBE2TEXT_BASE}/api/demo-key", timeout=15)
        api_key = key_response.get("apiKey") if isinstance(key_response, dict) else None
        if not api_key:
            raise FrontendError("Demo-key endpoint returned no API key")
        query = urlencode(
            {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "maxChars": 150000,
            }
        )
        payload = _fetch_json(
            f"{_YOUTUBE2TEXT_BASE}/api/transcribe?{query}",
            timeout=35,
            headers={"x-api-key": str(api_key)},
        )
        text = _find_transcript_text(payload)
        if not text:
            raise FrontendError("Response contained no transcript text")
        transcript = TranscriptData(
            source=source,
            language=None,
            language_code=None,
            is_generated=None,
            segments=[TranscriptSegment(text=text, start=0.0, duration=0.0)],
        )
        attempts.append({"source": source, "ok": True, "segment_count": 1})
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
    current_start: float | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_lines
        if current_start is not None:
            text = " ".join(part for part in current_lines if part).strip()
            if text:
                timed.append((current_start, text))
        current_start = None
        current_lines = []

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _TIMESTAMP_RE.match(line)
        if match:
            flush()
            hours = int(match.group("hours") or 0)
            minutes = int(match.group("minutes"))
            seconds = int(match.group("seconds"))
            current_start = float(hours * 3600 + minutes * 60 + seconds)
            current_lines = [match.group("text").strip()]
            continue
        if current_start is not None:
            current_lines.append(line)
        elif not line.startswith("#") and not _looks_like_metadata(line):
            untimed.append(line)
    flush()

    segments: list[TranscriptSegment] = []
    for index, (start, text) in enumerate(timed):
        next_start = timed[index + 1][0] if index + 1 < len(timed) else start + 3.0
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
            "channel": payload.get("author_name"),
            "channel_url": payload.get("author_url"),
            "thumbnail": payload.get("thumbnail_url"),
        }
    except Exception as exc:
        attempts.append({"source": "youtube oEmbed", "ok": False, "error": str(exc)})
        return {}


def fetch_youtube_data_api(
    video_id: str,
    api_key: str | None,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not api_key:
        attempts.append({"source": "YouTube Data API", "ok": False, "error": "no API key"})
        return {}, []

    metadata: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []
    try:
        query = urlencode(
            {"part": "snippet,statistics,contentDetails", "id": video_id, "key": api_key}
        )
        payload = _fetch_json(
            f"https://www.googleapis.com/youtube/v3/videos?{query}", timeout=20
        )
        item = (payload.get("items") or [None])[0]
        if item:
            snippet = item.get("snippet") or {}
            statistics = item.get("statistics") or {}
            thumbnails = snippet.get("thumbnails") or {}
            metadata = {
                "id": video_id,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "channel": snippet.get("channelTitle"),
                "channel_id": snippet.get("channelId"),
                "upload_date": (snippet.get("publishedAt") or "").replace("-", "")[:8],
                "tags": snippet.get("tags"),
                "categories": [snippet.get("categoryId")] if snippet.get("categoryId") else None,
                "view_count": _as_int(statistics.get("viewCount")),
                "like_count": _as_int(statistics.get("likeCount")),
                "comment_count": _as_int(statistics.get("commentCount")),
                "thumbnail": _best_api_thumbnail(thumbnails),
            }
            metadata = {key: value for key, value in metadata.items() if value is not None}
        attempts.append({"source": "YouTube Data API metadata", "ok": bool(metadata)})
    except Exception as exc:
        attempts.append({"source": "YouTube Data API metadata", "ok": False, "error": str(exc)})

    if comment_limit > 0:
        try:
            query = urlencode(
                {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, comment_limit),
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": api_key,
                }
            )
            payload = _fetch_json(
                f"https://www.googleapis.com/youtube/v3/commentThreads?{query}", timeout=25
            )
            for item in payload.get("items") or []:
                snippet = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                )
                text = str(snippet.get("textDisplay") or "").strip()
                if text:
                    comments.append(
                        {
                            "author": snippet.get("authorDisplayName"),
                            "text": text,
                            "like_count": snippet.get("likeCount"),
                            "timestamp": None,
                            "parent": None,
                        }
                    )
            attempts.append(
                {"source": "YouTube Data API comments", "ok": bool(comments), "count": len(comments)}
            )
        except Exception as exc:
            attempts.append({"source": "YouTube Data API comments", "ok": False, "error": str(exc)})
    return metadata, comments


def fetch_invidious_data(
    video_id: str,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    instances = list(_TRUSTED_INVIDIOUS)
    try:
        registry = _fetch_json(_INVIDIOUS_REGISTRY, timeout=15)
        discovered = _eligible_invidious_instances(registry)
        instances.extend(discovered)
        attempts.append(
            {
                "source": "Invidious registry",
                "ok": bool(discovered),
                "instance_count": len(discovered),
            }
        )
    except Exception as exc:
        attempts.append({"source": "Invidious registry", "ok": False, "error": str(exc)})

    instances = list(dict.fromkeys(uri.rstrip("/") for uri in instances))[:6]
    metadata: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []
    for base_uri in instances:
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
        payload = _fetch_json(f"{base_uri}/api/v1/videos/{video_id}", timeout=12)
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
        payload = _fetch_json(endpoint, timeout=15)
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
            if item.get("content") or item.get("contentHtml")
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


def _fetch_json(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> Any:
    return json.loads(_fetch_text(url, timeout=timeout, headers=headers))


def _fetch_text(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise FrontendError("Only HTTPS frontend URLs are allowed")
    request_headers = {"User-Agent": _USER_AGENT, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed/validated hosts
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise FrontendError("Frontend response exceeded the 8 MiB safety limit")
    return payload.decode("utf-8", errors="replace")


def _looks_like_metadata(line: str) -> bool:
    lowered = line.lower()
    prefixes = (
        "title:",
        "source:",
        "source video:",
        "language:",
        "duration:",
        "word count:",
        "words:",
        "available languages:",
        "other available languages:",
        "to request a specific language:",
        "video id:",
        "url:",
    )
    return lowered.startswith(prefixes)


def _find_transcript_text(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("transcript", "text", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and len(candidate.strip()) >= 20:
                return candidate.strip()
        for candidate in value.values():
            found = _find_transcript_text(candidate)
            if found:
                return found
    elif isinstance(value, list):
        text_parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = item.get("text") or item.get("content")
                if isinstance(candidate, str) and candidate.strip():
                    text_parts.append(candidate.strip())
        if text_parts:
            return " ".join(text_parts)
        for item in value:
            found = _find_transcript_text(item)
            if found:
                return found
    return None


def _best_thumbnail(value: Any) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    candidates = [item for item in value if isinstance(item, dict) and item.get("url")]
    if not candidates:
        return None
    return str(max(candidates, key=lambda item: int(item.get("width") or 0))["url"])


def _best_api_thumbnail(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("maxres", "standard", "high", "medium", "default"):
        item = value.get(key)
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
