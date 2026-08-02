from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
_USER_AGENT = "AITubeTranscript/0.3 (+https://github.com/organicoverlords/AITubeTranscript)"
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_CATALOG_MAX_VIDEOS = 5_000
MAX_CATALOG_VIDEOS = 20_000


class InvalidChannelReference(ValueError):
    pass


def parse_channel_reference(value: str) -> tuple[str, str]:
    candidate = value.strip()
    if _CHANNEL_ID_RE.fullmatch(candidate):
        return "id", candidate
    if _HANDLE_RE.fullmatch(candidate):
        return "forHandle", candidate

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise InvalidChannelReference(
            "Use a YouTube channel ID, @handle, /channel/ URL, /@handle URL, or /user/ URL"
        )

    query_channel = (parse_qs(parsed.query).get("channel_id") or [None])[0]
    if query_channel and _CHANNEL_ID_RE.fullmatch(query_channel):
        return "id", query_channel

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel" and _CHANNEL_ID_RE.fullmatch(parts[1]):
        return "id", parts[1]
    if parts and parts[0].startswith("@") and _HANDLE_RE.fullmatch(parts[0]):
        return "forHandle", parts[0]
    if len(parts) >= 2 and parts[0] == "user" and _USERNAME_RE.fullmatch(parts[1]):
        return "forUsername", parts[1]

    raise InvalidChannelReference(
        "Custom /c/ channel URLs are ambiguous. Use the channel's @handle or /channel/UC... URL."
    )


def fetch_channel_catalog(
    value: str,
    api_key: str | None,
    *,
    start_index: int = 0,
    limit: int = DEFAULT_CATALOG_MAX_VIDEOS,
) -> dict[str, Any]:
    if not api_key:
        raise InvalidChannelReference(
            "YOUTUBE_API_KEY is required to list a channel's uploads"
        )
    if start_index < 0:
        raise InvalidChannelReference("start_index must be zero or greater")
    if not 1 <= limit <= MAX_CATALOG_VIDEOS:
        raise InvalidChannelReference(
            f"limit must be between 1 and {MAX_CATALOG_VIDEOS}"
        )

    channel = _resolve_channel(value, api_key)
    uploads_playlist_id = channel["uploads_playlist_id"]
    selected_items, listing = _list_upload_items(
        uploads_playlist_id,
        api_key,
        start_index=start_index,
        limit=limit,
    )
    video_ids = [item["video_id"] for item in selected_items]
    details = _video_details(video_ids, api_key)

    videos: list[dict[str, Any]] = []
    unavailable_count = 0
    for selected_index, item in enumerate(selected_items, start=1):
        video_id = item["video_id"]
        detail = details.get(video_id)
        if detail is None:
            unavailable_count += 1
            videos.append(
                {
                    "index": selected_index,
                    "channel_upload_index": start_index + selected_index,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": item.get("title") or "Unavailable video",
                    "published_at": item.get("published_at"),
                    "published_date": _date_only(item.get("published_at")),
                    "duration": None,
                    "duration_seconds": None,
                    "duration_display": None,
                    "view_count": None,
                    "like_count": None,
                    "comment_count": None,
                    "privacy_status": item.get("privacy_status"),
                    "availability": "UNAVAILABLE_OR_PRIVATE",
                }
            )
            continue

        detail["index"] = selected_index
        detail["channel_upload_index"] = start_index + selected_index
        videos.append(detail)

    expected_indices = list(range(1, len(videos) + 1))
    actual_indices = [int(video["index"]) for video in videos]
    catalog_complete = listing["catalog_exhausted"]
    status = "PROVEN" if catalog_complete and unavailable_count == 0 else "PARTIAL"
    fetched_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "1.0",
        "status": status,
        "fetched_at": fetched_at,
        "requested_reference": value,
        "channel": channel,
        "selection": {
            "start_index": start_index,
            "limit": limit,
            "selected_count": len(videos),
            "catalog_items_seen": listing["catalog_items_seen"],
            "api_pages": listing["api_pages"],
            "catalog_exhausted": catalog_complete,
            "truncated_by_limit": listing["truncated_by_limit"],
            "next_start_index": (
                None if catalog_complete else start_index + len(videos)
            ),
        },
        "unavailable_video_count": unavailable_count,
        "coverage": {
            "status": "PROVEN" if actual_indices == expected_indices else "REJECTED",
            "exactly_once": actual_indices == expected_indices,
            "missing_indices": sorted(set(expected_indices) - set(actual_indices)),
            "duplicate_indices": sorted(
                index for index in set(actual_indices) if actual_indices.count(index) > 1
            ),
            "unexpected_indices": sorted(set(actual_indices) - set(expected_indices)),
            "ordered_contiguous": actual_indices == expected_indices,
        },
        "videos": videos,
    }


def write_channel_catalog(catalog: dict[str, Any], output_root: Path) -> Path:
    channel_id = str(catalog["channel"]["channel_id"])
    destination = output_root / "channels" / channel_id
    destination.mkdir(parents=True, exist_ok=True)

    jsonl = "".join(
        json.dumps(video, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
        for video in catalog["videos"]
    )
    markdown = _catalog_markdown(catalog)
    catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    files = {
        "channel-catalog.json": catalog_json,
        "channel-videos.jsonl": jsonl,
        "channel-videos.md": markdown,
    }
    for name, content in files.items():
        (destination / name).write_text(content, encoding="utf-8")

    receipt = {
        "schema_version": "1.0",
        "status": catalog["status"],
        "channel_id": channel_id,
        "channel_title": catalog["channel"].get("title"),
        "fetched_at": catalog["fetched_at"],
        "video_count": len(catalog["videos"]),
        "unavailable_video_count": catalog["unavailable_video_count"],
        "catalog_exhausted": catalog["selection"]["catalog_exhausted"],
        "truncated_by_limit": catalog["selection"]["truncated_by_limit"],
        "next_start_index": catalog["selection"]["next_start_index"],
        "coverage": catalog["coverage"],
        "private_result_path": f"channels/{channel_id}/latest/",
        "read_order": [
            "channel-receipt.json",
            "channel-videos.md",
            "channel-videos.jsonl",
            "channel-catalog.json",
        ],
        "sha256": {
            name: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for name, content in sorted(files.items())
        },
    }
    (destination / "channel-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _resolve_channel(value: str, api_key: str) -> dict[str, Any]:
    filter_name, filter_value = parse_channel_reference(value)
    query = urlencode(
        {
            "part": "snippet,contentDetails,statistics",
            filter_name: filter_value,
            "key": api_key,
        }
    )
    payload = _fetch_json(
        f"https://www.googleapis.com/youtube/v3/channels?{query}",
        timeout=20,
    )
    items = payload.get("items") or []
    if len(items) != 1:
        raise InvalidChannelReference("Channel reference did not resolve to exactly one channel")

    item = items[0]
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    related = content.get("relatedPlaylists") or {}
    statistics = item.get("statistics") or {}
    channel_id = str(item.get("id") or "").strip()
    uploads_playlist_id = str(related.get("uploads") or "").strip()
    if not _CHANNEL_ID_RE.fullmatch(channel_id) or not uploads_playlist_id:
        raise InvalidChannelReference("Resolved channel did not expose an uploads playlist")

    custom_url = snippet.get("customUrl")
    return {
        "channel_id": channel_id,
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "custom_url": custom_url,
        "channel_url": (
            f"https://www.youtube.com/{custom_url}"
            if custom_url
            else f"https://www.youtube.com/channel/{channel_id}"
        ),
        "published_at": snippet.get("publishedAt"),
        "country": snippet.get("country"),
        "uploads_playlist_id": uploads_playlist_id,
        "view_count": _as_int(statistics.get("viewCount")),
        "subscriber_count": _as_int(statistics.get("subscriberCount")),
        "hidden_subscriber_count": bool(statistics.get("hiddenSubscriberCount", False)),
        "reported_video_count": _as_int(statistics.get("videoCount")),
    }


def _list_upload_items(
    playlist_id: str,
    api_key: str,
    *,
    start_index: int,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    skipped = 0
    page_token: str | None = None
    exhausted = False
    api_pages = 0
    catalog_items_seen = 0

    while len(selected) < limit:
        parameters = {
            "part": "snippet,contentDetails,status",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            parameters["pageToken"] = page_token
        payload = _fetch_json(
            "https://www.googleapis.com/youtube/v3/playlistItems?"
            + urlencode(parameters),
            timeout=25,
        )
        api_pages += 1
        for item in payload.get("items") or []:
            content = item.get("contentDetails") or {}
            snippet = item.get("snippet") or {}
            status = item.get("status") or {}
            video_id = str(content.get("videoId") or "").strip()
            if not video_id:
                continue
            catalog_items_seen += 1
            if skipped < start_index:
                skipped += 1
                continue
            selected.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "published_at": (
                        content.get("videoPublishedAt") or snippet.get("publishedAt")
                    ),
                    "privacy_status": status.get("privacyStatus"),
                }
            )
            if len(selected) >= limit:
                break

        next_page = str(payload.get("nextPageToken") or "").strip()
        if not next_page:
            exhausted = True
            page_token = None
            break
        page_token = next_page

    return selected, {
        "catalog_items_seen": catalog_items_seen,
        "api_pages": api_pages,
        "catalog_exhausted": exhausted,
        "truncated_by_limit": not exhausted and len(selected) >= limit,
        "next_page_token_present": bool(page_token),
    }


def _video_details(video_ids: list[str], api_key: str) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(video_ids), 50):
        chunk = video_ids[offset : offset + 50]
        query = urlencode(
            {
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(chunk),
                "key": api_key,
            }
        )
        payload = _fetch_json(
            f"https://www.googleapis.com/youtube/v3/videos?{query}",
            timeout=25,
        )
        for item in payload.get("items") or []:
            video_id = str(item.get("id") or "").strip()
            if not video_id:
                continue
            snippet = item.get("snippet") or {}
            content = item.get("contentDetails") or {}
            statistics = item.get("statistics") or {}
            status = item.get("status") or {}
            duration = content.get("duration")
            seconds = _iso8601_duration_seconds(duration)
            published_at = snippet.get("publishedAt")
            details[video_id] = {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "published_at": published_at,
                "published_date": _date_only(published_at),
                "duration": duration,
                "duration_seconds": seconds,
                "duration_display": _duration_display(seconds),
                "view_count": _as_int(statistics.get("viewCount")),
                "like_count": _as_int(statistics.get("likeCount")),
                "comment_count": _as_int(statistics.get("commentCount")),
                "privacy_status": status.get("privacyStatus"),
                "live_broadcast_content": snippet.get("liveBroadcastContent"),
                "availability": "PUBLIC_API_VISIBLE",
            }
    return details


def _catalog_markdown(catalog: dict[str, Any]) -> str:
    channel = catalog["channel"]
    selection = catalog["selection"]
    lines = [
        f"# {channel.get('title') or channel['channel_id']} — video catalog",
        "",
        f"- Channel ID: `{channel['channel_id']}`",
        f"- Fetched: {catalog['fetched_at']}",
        f"- Selected videos: {selection['selected_count']}",
        f"- Catalog exhausted: {selection['catalog_exhausted']}",
        f"- Next start index: {selection['next_start_index']}",
        "",
        "| # | Published | Duration | Title | Video ID | Views |",
        "|---:|---|---:|---|---|---:|",
    ]
    for video in catalog["videos"]:
        title = str(video.get("title") or "Unavailable video").replace("|", "\\|")
        lines.append(
            "| {index} | {published} | {duration} | {title} | `{video_id}` | {views} |".format(
                index=video["channel_upload_index"],
                published=video.get("published_date") or "—",
                duration=video.get("duration_display") or "—",
                title=title,
                video_id=video["video_id"],
                views=video.get("view_count") if video.get("view_count") is not None else "—",
            )
        )
    return "\n".join(lines) + "\n"


def _iso8601_duration_seconds(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?",
        value,
    )
    if not match:
        return None
    return (
        int(match.group("days") or 0) * 86_400
        + int(match.group("hours") or 0) * 3_600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def _duration_display(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hours, remainder = divmod(seconds, 3_600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _date_only(value: Any) -> str | None:
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _fetch_json(url: str, *, timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise RuntimeError("YouTube API response exceeded the safety limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("YouTube API response was not a JSON object")
    if payload.get("error"):
        message = str((payload["error"] or {}).get("message") or "unknown API error")
        raise RuntimeError(f"YouTube API error: {message}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitube-channel",
        description=(
            "List a YouTube channel's public uploads with titles, publication dates, "
            "durations, and snapshot statistics."
        ),
    )
    parser.add_argument("channel", help="Channel ID, @handle, or YouTube channel URL")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-videos", type=int, default=DEFAULT_CATALOG_MAX_VIDEOS)
    parser.add_argument(
        "--youtube-api-key",
        default=os.environ.get("YOUTUBE_API_KEY"),
        help="YouTube Data API key; defaults to YOUTUBE_API_KEY",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = fetch_channel_catalog(
            args.channel,
            args.youtube_api_key,
            start_index=args.start_index,
            limit=args.max_videos,
        )
        destination = write_channel_catalog(catalog, args.output)
    except Exception as exc:
        print(f"AITubeTranscript channel catalog failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    else:
        print(f"CHANNEL_ID={catalog['channel']['channel_id']}")
        print(f"CHANNEL_TITLE={catalog['channel'].get('title') or ''}")
        print(f"CATALOG_STATUS={catalog['status']}")
        print(f"VIDEO_COUNT={len(catalog['videos'])}")
        print(f"CATALOG_EXHAUSTED={str(catalog['selection']['catalog_exhausted']).lower()}")
        print(f"NEXT_START_INDEX={catalog['selection']['next_start_index'] or ''}")
        print(f"OUTPUT_DIR={destination}")
    return 0 if catalog["status"] == "PROVEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
