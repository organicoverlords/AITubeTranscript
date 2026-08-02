from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .frontends import (
    fetch_invidious_data,
    fetch_oembed,
    fetch_transcript_proxy,
    fetch_youtube_data_api,
)
from .models import CommentData, ResearchBundle
from .piped import fetch_piped_data
from .youtube import canonical_url, extract_video_id


def fetch_youtube_cloud(
    value: str,
    *,
    languages: tuple[str, ...] = ("en",),
    comment_limit: int = 100,
    include_comments: bool = True,
    youtube_api_key: str | None = None,
) -> ResearchBundle:
    """Fetch the private GitHub cloud path without optional third-party packages."""
    video_id = extract_video_id(value)
    url = canonical_url(video_id)
    attempts: list[dict[str, Any]] = [
        {"source": "fast cloud path", "ok": True}
    ]
    warnings: list[str] = []
    info: dict[str, Any] = {"id": video_id, "webpage_url": url}

    transcript = fetch_transcript_proxy(video_id, languages, attempts)
    if transcript is not None:
        warnings.append(
            "Transcript was retrieved through a third-party public edge service; "
            "verify important quotations against the video."
        )
    else:
        warnings.append(
            "No transcript was retrieved through the dependency-free cloud path."
        )

    requested_comments = max(0, comment_limit) if include_comments else 0
    api_metadata, comments = fetch_youtube_data_api(
        video_id,
        youtube_api_key,
        requested_comments,
        attempts,
    )
    _merge_missing(info, api_metadata)

    if not info.get("title"):
        _merge_missing(info, fetch_oembed(url, attempts))

    needs_metadata = not info.get("description")
    needs_comments = include_comments and not comments
    if needs_metadata or needs_comments:
        piped_metadata, piped_comments = fetch_piped_data(
            video_id,
            requested_comments if needs_comments else 0,
            attempts,
        )
        _merge_missing(info, piped_metadata)
        if piped_comments and not comments:
            comments = piped_comments

    needs_metadata = not info.get("description")
    needs_comments = include_comments and not comments
    if needs_metadata or needs_comments:
        frontend_metadata, frontend_comments = fetch_invidious_data(
            video_id,
            requested_comments if needs_comments else 0,
            attempts,
        )
        _merge_missing(info, frontend_metadata)
        if frontend_comments and not comments:
            comments = frontend_comments

    normalized_comments = _normalize_comments(comments, requested_comments)
    if include_comments and not normalized_comments:
        warnings.append(
            "No comments were returned. Configure YOUTUBE_API_KEY or use the "
            "standard fetch path."
        )

    return ResearchBundle(
        schema_version="1.1",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        video_id=video_id,
        canonical_url=url,
        metadata=_clean_metadata(info),
        transcript=transcript,
        comments=normalized_comments,
        warnings=warnings,
        attempts=attempts,
    )


def _merge_missing(target: dict[str, Any], fallback: dict[str, Any]) -> None:
    for key, value in fallback.items():
        if value is not None and not target.get(key):
            target[key] = value


def _normalize_comments(
    raw: list[dict[str, Any]],
    limit: int,
) -> list[CommentData]:
    comments: list[CommentData] = []
    for item in raw[: max(0, limit)]:
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        comments.append(
            CommentData(
                author=item.get("author"),
                text=text,
                like_count=_as_int(item.get("like_count")),
                timestamp=_as_int(item.get("timestamp")),
                parent=item.get("parent"),
            )
        )
    return comments


def _clean_metadata(info: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "title",
        "description",
        "channel",
        "channel_id",
        "channel_url",
        "uploader",
        "upload_date",
        "timestamp",
        "published",
        "duration",
        "duration_string",
        "view_count",
        "like_count",
        "comment_count",
        "availability",
        "age_limit",
        "categories",
        "tags",
        "thumbnail",
        "webpage_url",
    )
    return {key: info.get(key) for key in keys if info.get(key) is not None}


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
