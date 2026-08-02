from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

from .models import CommentData, TranscriptData, TranscriptSegment

_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_TIMESTAMP_RE = re.compile(
    r"^\[(?P<time>(?:\d+:)?\d{1,2}:\d{2}(?:[.,]\d+)?)\]\s*(?P<text>.*)$"
)
_LANGUAGE_RE = re.compile(r"^Language:\s*([^·\n]+)", re.MULTILINE | re.IGNORECASE)
_DEFAULT_INVIDIOUS = (
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yt.chocolatemoo53.com",
)


@dataclass(slots=True)
class ProviderResult:
    metadata: dict[str, Any]
    transcript: TranscriptData | None
    comments: list[CommentData]


def fetch_hosted_transcript(
    video_id: str,
    languages: tuple[str, ...],
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    """Try low-volume public transcript relays after direct YouTube routes fail."""
    transcript = _fetch_youtube_transcript_ai(video_id, languages, attempts)
    if transcript is not None:
        return transcript
    return _fetch_youtube2text(video_id, attempts)


def fetch_oembed_metadata(
    video_id: str, attempts: list[dict[str, Any]]
) -> dict[str, Any]:
    query = urlencode(
        {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "format": "json",
        }
    )
    try:
        data = _get_json(f"https://www.youtube.com/oembed?{query}")
        metadata = {
            "id": video_id,
            "title": data.get("title"),
            "channel": data.get("author_name"),
            "uploader": data.get("author_name"),
            "channel_url": data.get("author_url"),
            "thumbnail": data.get("thumbnail_url"),
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        }
        attempts.append({"source": "youtube-oembed", "ok": bool(metadata.get("title"))})
        return {key: value for key, value in metadata.items() if value is not None}
    except Exception as exc:
        attempts.append({"source": "youtube-oembed", "ok": False, "error": str(exc)})
        return {}


def fetch_invidious(
    video_id: str,
    languages: tuple[str, ...],
    comment_limit: int,
    attempts: list[dict[str, Any]],
    configured_instances: tuple[str, ...] = (),
) -> ProviderResult:
    best_metadata: dict[str, Any] = {}
    best_comments: list[CommentData] = []
    transcript: TranscriptData | None = None
    instances = _invidious_instances(configured_instances, attempts)

    for instance in instances:
        instance = instance.rstrip("/")
        instance_responded = False
        if not best_metadata:
            try:
                video = _get_json(f"{instance}/api/v1/videos/{video_id}")
                best_metadata = _normalize_invidious_metadata(video, video_id)
                instance_responded = bool(best_metadata.get("title"))
                attempts.append(
                    {
                        "source": f"invidious metadata:{instance}",
                        "ok": instance_responded,
                    }
                )
            except Exception as exc:
                attempts.append(
                    {"source": f"invidious metadata:{instance}", "ok": False, "error": str(exc)}
                )

        if transcript is None:
            try:
                transcript = _fetch_invidious_captions(instance, video_id, languages)
                caption_ok = transcript is not None and bool(transcript.segments)
                instance_responded = instance_responded or caption_ok
                attempts.append(
                    {
                        "source": f"invidious captions:{instance}",
                        "ok": caption_ok,
                    }
                )
            except Exception as exc:
                attempts.append(
                    {"source": f"invidious captions:{instance}", "ok": False, "error": str(exc)}
                )

        if comment_limit > 0 and not best_comments and instance_responded:
            try:
                payload = _get_json(
                    f"{instance}/api/v1/comments/{video_id}?sort_by=top&thin_mode=true"
                )
                best_comments = _normalize_invidious_comments(
                    payload.get("comments") or [], comment_limit
                )
                attempts.append(
                    {
                        "source": f"invidious comments:{instance}",
                        "ok": bool(best_comments),
                        "count": len(best_comments),
                    }
                )
            except Exception as exc:
                attempts.append(
                    {"source": f"invidious comments:{instance}", "ok": False, "error": str(exc)}
                )

        if best_metadata and transcript is not None and (comment_limit == 0 or best_comments):
            break

    return ProviderResult(best_metadata, transcript, best_comments)


def fetch_youtube_data_api(
    video_id: str,
    api_key: str | None,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> ProviderResult:
    if not api_key:
        return ProviderResult({}, None, [])
    metadata: dict[str, Any] = {}
    comments: list[CommentData] = []
    try:
        query = urlencode(
            {"part": "snippet,statistics,contentDetails", "id": video_id, "key": api_key}
        )
        payload = _get_json(f"https://www.googleapis.com/youtube/v3/videos?{query}")
        item = (payload.get("items") or [None])[0]
        if item:
            snippet = item.get("snippet") or {}
            statistics = item.get("statistics") or {}
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
                "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
            }
            metadata = {key: value for key, value in metadata.items() if value is not None}
        attempts.append({"source": "youtube-data-api metadata", "ok": bool(metadata)})
    except Exception as exc:
        attempts.append({"source": "youtube-data-api metadata", "ok": False, "error": str(exc)})

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
            payload = _get_json(f"https://www.googleapis.com/youtube/v3/commentThreads?{query}")
            for item in payload.get("items") or []:
                snippet = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                )
                text = str(snippet.get("textDisplay") or "").strip()
                if text:
                    comments.append(
                        CommentData(
                            author=snippet.get("authorDisplayName"),
                            text=text,
                            like_count=_as_int(snippet.get("likeCount")),
                        )
                    )
            attempts.append(
                {"source": "youtube-data-api comments", "ok": bool(comments), "count": len(comments)}
            )
        except Exception as exc:
            attempts.append({"source": "youtube-data-api comments", "ok": False, "error": str(exc)})
    return ProviderResult(metadata, None, comments)


def parse_timestamped_markdown(
    payload: str, source: str, language_code: str | None = None
) -> TranscriptData:
    cues: list[tuple[float, str]] = []
    current_start: float | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_lines
        if current_start is not None:
            text = " ".join(part.strip() for part in current_lines if part.strip()).strip()
            if text:
                cues.append((current_start, text))
        current_start = None
        current_lines = []

    for raw_line in payload.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        match = _TIMESTAMP_RE.match(line)
        if match:
            flush()
            current_start = _parse_timestamp(match.group("time"))
            current_lines = [match.group("text")]
        elif current_start is not None and line:
            current_lines.append(line)
    flush()

    segments: list[TranscriptSegment] = []
    for index, (start, text) in enumerate(cues):
        next_start = cues[index + 1][0] if index + 1 < len(cues) else start + 3.0
        segments.append(
            TranscriptSegment(text=text, start=start, duration=max(0.0, next_start - start))
        )
    return TranscriptData(
        source=source,
        language=language_code,
        language_code=language_code,
        is_generated=None,
        segments=segments,
    )


def _fetch_youtube_transcript_ai(
    video_id: str,
    languages: tuple[str, ...],
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    choices: list[str | None] = list(dict.fromkeys((*languages, None)))
    for language in choices:
        suffix = f"?{urlencode({'lang': language})}" if language else ""
        url = f"https://youtube-transcript.ai/transcript/{quote(video_id)}.txt{suffix}"
        label = f"youtube-transcript.ai:{language or 'default'}"
        try:
            payload = _get_text(url)
            if payload.lstrip().lower().startswith(("<!doctype", "<html")):
                raise ValueError("provider returned HTML instead of a transcript")
            header_language = _LANGUAGE_RE.search(payload)
            language_code = header_language.group(1).strip() if header_language else language
            transcript = parse_timestamped_markdown(payload, label, language_code)
            if not transcript.segments:
                raise ValueError("provider response contained no timestamped cues")
            attempts.append(
                {"source": label, "ok": True, "segment_count": len(transcript.segments)}
            )
            return transcript
        except Exception as exc:
            attempts.append({"source": label, "ok": False, "error": str(exc)})
    return None


def _fetch_youtube2text(
    video_id: str, attempts: list[dict[str, Any]]
) -> TranscriptData | None:
    try:
        key_payload = _get_json("https://youtube2text.org/api/demo-key")
        api_key = key_payload.get("apiKey")
        if not api_key:
            raise ValueError("demo key endpoint returned no apiKey")
        query = urlencode(
            {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "maxChars": 150000,
            }
        )
        payload = _get_json(
            f"https://youtube2text.org/api/transcribe?{query}",
            headers={"x-api-key": str(api_key)},
        )
        text = _find_transcript_text(payload)
        if not text:
            raise ValueError("provider response contained no transcript text")
        transcript = TranscriptData(
            source="youtube2text.org",
            language=None,
            language_code=None,
            is_generated=None,
            segments=[TranscriptSegment(text=text.strip(), start=0.0, duration=0.0)],
        )
        attempts.append({"source": "youtube2text.org", "ok": True, "segment_count": 1})
        return transcript
    except Exception as exc:
        attempts.append({"source": "youtube2text.org", "ok": False, "error": str(exc)})
        return None


def _fetch_invidious_captions(
    instance: str, video_id: str, languages: tuple[str, ...]
) -> TranscriptData | None:
    listing = _get_json(f"{instance}/api/v1/captions/{video_id}")
    tracks = listing.get("captions") or []
    selected: dict[str, Any] | None = None
    for language in languages:
        selected = next(
            (
                item
                for item in tracks
                if str(item.get("languageCode") or "").lower() == language.lower()
                or str(item.get("languageCode") or "").lower().startswith(language.lower() + "-")
            ),
            None,
        )
        if selected:
            break
    selected = selected or (tracks[0] if tracks else None)
    if not selected:
        return None
    track_url = selected.get("url")
    if not track_url:
        return None
    payload = _get_text(urljoin(instance + "/", str(track_url)))
    from .captions import parse_vtt

    transcript = parse_vtt(
        payload.encode("utf-8"),
        f"invidious captions:{instance}",
        selected.get("languageCode"),
    )
    return transcript if transcript.segments else None


def _invidious_instances(
    configured: tuple[str, ...], attempts: list[dict[str, Any]]
) -> tuple[str, ...]:
    instances = list(configured) + list(_DEFAULT_INVIDIOUS)
    try:
        payload = _get_json("https://api.invidious.io/instances.json")
        for item in payload:
            if not isinstance(item, list) or len(item) != 2:
                continue
            host, details = item
            if not isinstance(details, dict) or not details.get("api"):
                continue
            uri = str(details.get("uri") or f"https://{host}")
            if uri.startswith("https://"):
                instances.append(uri)
        attempts.append({"source": "invidious instance discovery", "ok": True})
    except Exception as exc:
        attempts.append({"source": "invidious instance discovery", "ok": False, "error": str(exc)})
    return tuple(dict.fromkeys(value.rstrip("/") for value in instances if value))[:5]


def _normalize_invidious_metadata(data: dict[str, Any], video_id: str) -> dict[str, Any]:
    metadata = {
        "id": video_id,
        "title": data.get("title"),
        "description": data.get("description"),
        "channel": data.get("author"),
        "channel_id": data.get("authorId"),
        "channel_url": data.get("authorUrl"),
        "duration": data.get("lengthSeconds"),
        "view_count": data.get("viewCount"),
        "like_count": data.get("likeCount"),
        "comment_count": data.get("commentCount"),
        "published": data.get("published"),
        "published_text": data.get("publishedText"),
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    thumbnails = data.get("videoThumbnails") or []
    if thumbnails:
        metadata["thumbnail"] = thumbnails[-1].get("url")
    return {key: value for key, value in metadata.items() if value is not None}


def _normalize_invidious_comments(raw: list[dict[str, Any]], limit: int) -> list[CommentData]:
    result: list[CommentData] = []
    for item in raw[: max(0, limit)]:
        text = str(item.get("content") or "").strip()
        if text:
            result.append(
                CommentData(
                    author=item.get("author"),
                    text=text,
                    like_count=_as_int(item.get("likeCount")),
                    timestamp=_as_int(item.get("published")),
                    parent=item.get("parent"),
                )
            )
    return result


def _get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    return json.loads(_get_text(url, headers=headers))


def _get_text(url: str, headers: dict[str, str] | None = None) -> str:
    request_headers = {
        "Accept": "application/json,text/plain,text/vtt,*/*",
        "User-Agent": "AITubeTranscript/0.2 (+https://github.com/organicoverlords/AITubeTranscript)",
    }
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed trusted provider URLs
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ValueError("provider response exceeded 8 MiB safety limit")
        charset = response.headers.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def _parse_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        raise ValueError(f"invalid timestamp: {value}")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _find_transcript_text(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("transcript", "text", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and len(candidate.strip()) > 40:
                return candidate
        for candidate in value.values():
            found = _find_transcript_text(candidate)
            if found:
                return found
    elif isinstance(value, list):
        texts = []
        for item in value:
            if isinstance(item, dict):
                candidate = item.get("text") or item.get("content")
                if isinstance(candidate, str) and candidate.strip():
                    texts.append(candidate.strip())
        if texts:
            return " ".join(texts)
        for item in value:
            found = _find_transcript_text(item)
            if found:
                return found
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
