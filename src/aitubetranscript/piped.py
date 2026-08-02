from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_TAG_RE = re.compile(r"<[^>]+>")
_USER_AGENT = "AITubeTranscript/0.2 (+https://github.com/organicoverlords/AITubeTranscript)"
_PIPED_INSTANCES = (
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.nosebs.ru",
    "https://pipedapi-libre.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.adminforge.de",
)


def fetch_piped_data(
    video_id: str,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Retrieve public metadata and comments through Piped API instances."""
    metadata: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []

    for instance in _PIPED_INSTANCES:
        host = urlparse(instance).hostname or instance
        if not metadata:
            try:
                payload = _fetch_json(
                    f"{instance}/streams/{quote(video_id)}",
                    timeout=8,
                )
                metadata = _normalize_metadata(payload, video_id)
                attempts.append(
                    {
                        "source": f"Piped streams:{host}",
                        "ok": bool(metadata.get("title")),
                    }
                )
            except Exception as exc:
                attempts.append(
                    {"source": f"Piped streams:{host}", "ok": False, "error": str(exc)}
                )

        if comment_limit > 0 and not comments:
            try:
                payload = _fetch_json(
                    f"{instance}/comments/{quote(video_id)}",
                    timeout=8,
                )
                comments = _normalize_comments(
                    payload.get("comments") or [],
                    comment_limit,
                )
                attempts.append(
                    {
                        "source": f"Piped comments:{host}",
                        "ok": bool(comments),
                        "count": len(comments),
                        "disabled": bool(payload.get("disabled")),
                    }
                )
            except Exception as exc:
                attempts.append(
                    {"source": f"Piped comments:{host}", "ok": False, "error": str(exc)}
                )

        if metadata and (comment_limit <= 0 or comments):
            break

    return metadata, comments


def _normalize_metadata(payload: dict[str, Any], video_id: str) -> dict[str, Any]:
    uploader_url = payload.get("uploaderUrl")
    channel_id = None
    if isinstance(uploader_url, str) and "/channel/" in uploader_url:
        channel_id = uploader_url.rsplit("/channel/", 1)[-1].split("?", 1)[0]

    metadata = {
        "id": video_id,
        "title": payload.get("title"),
        "description": payload.get("description"),
        "channel": payload.get("uploader"),
        "uploader": payload.get("uploader"),
        "channel_id": channel_id,
        "channel_url": uploader_url,
        "duration": payload.get("duration"),
        "view_count": payload.get("views"),
        "like_count": payload.get("likes"),
        "upload_date": payload.get("uploadDate"),
        "thumbnail": payload.get("thumbnailUrl"),
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    return {key: value for key, value in metadata.items() if value not in (None, "")}


def _normalize_comments(raw: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for item in raw[: max(0, limit)]:
        text = _clean_text(item.get("commentText"))
        if not text:
            continue
        comments.append(
            {
                "author": item.get("author"),
                "text": text,
                "like_count": _as_int(item.get("likeCount")),
                "timestamp": None,
                "parent": None,
            }
        )
    return comments


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _fetch_json(url: str, timeout: int) -> Any:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only public HTTPS Piped endpoints are allowed")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted hosts
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError("Piped response exceeded the 8 MiB safety limit")
    return json.loads(payload.decode("utf-8", errors="replace"))


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
