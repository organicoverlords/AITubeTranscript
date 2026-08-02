from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIDEO_INDEX = Path("memory/video-index.jsonl")
CHANNEL_INDEX = Path("memory/channel-index.jsonl")
BATCH_INDEX = Path("memory/batch-index.jsonl")


def update_memory_bank(
    vault: Path,
    *,
    batch_receipt: Path | None = None,
    video_ids: list[str] | None = None,
    channel_ids: list[str] | None = None,
    rebuild_all: bool = False,
) -> dict[str, int]:
    vault = vault.resolve()
    memory_root = vault / "memory"
    memory_root.mkdir(parents=True, exist_ok=True)

    selected_video_ids = set(video_ids or [])
    selected_channel_ids = set(channel_ids or [])
    selected_batch_ids: set[str] = set()

    if batch_receipt:
        receipt = _read_json(batch_receipt)
        selected_batch_ids.add(str(receipt["batch_id"]))
        selected_video_ids.update(
            str(result["video_id"])
            for result in receipt.get("results", [])
            if result.get("status") != "FAILED"
        )
        selected_channel_ids.update(
            str(channel["channel_id"])
            for channel in receipt.get("channel_catalogs", [])
        )

    if rebuild_all:
        selected_video_ids.update(
            path.parent.parent.name
            for path in (vault / "videos").glob("*/latest/receipt.json")
        )
        selected_channel_ids.update(
            path.parent.parent.name
            for path in (vault / "channels").glob("*/latest/channel-receipt.json")
        )
        selected_batch_ids.update(
            path.parent.parent.name
            for path in (vault / "batches").glob("*/latest/batch-receipt.json")
        )

    videos = _load_index(vault / VIDEO_INDEX, "video_id")
    channels = _load_index(vault / CHANNEL_INDEX, "channel_id")
    batches = _load_index(vault / BATCH_INDEX, "batch_id")

    for video_id in sorted(selected_video_ids):
        video_root = vault / "videos" / video_id / "latest"
        if not (video_root / "receipt.json").is_file():
            continue
        previous = videos.get(video_id)
        entry = ensure_video_memory_entry(video_root)
        videos[video_id] = entry
        _write_video_pointers(vault, entry, previous)

    for channel_id in sorted(selected_channel_ids):
        channel_root = vault / "channels" / channel_id / "latest"
        if not (channel_root / "channel-receipt.json").is_file():
            continue
        entry = _channel_memory_entry(channel_root)
        channels[channel_id] = entry
        _write_json(
            memory_root / "by-channel-id" / f"{channel_id}.json",
            entry,
        )

    for batch_id in sorted(selected_batch_ids):
        batch_root = vault / "batches" / batch_id / "latest"
        if not (batch_root / "batch-receipt.json").is_file():
            continue
        entry = _batch_memory_entry(batch_root)
        batches[batch_id] = entry
        _write_json(
            memory_root / "by-batch-id" / f"{_safe_component(batch_id, 100)}.json",
            entry,
        )

    ordered_videos = sorted(
        videos.values(),
        key=lambda item: (
            str(item.get("published_date") or ""),
            str(item.get("fetched_at") or ""),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    ordered_channels = sorted(
        channels.values(),
        key=lambda item: (
            str(item.get("fetched_at") or ""),
            str(item.get("channel_title") or ""),
        ),
        reverse=True,
    )
    ordered_batches = sorted(
        batches.values(),
        key=lambda item: str(item.get("completed_at") or ""),
        reverse=True,
    )

    _write_jsonl(vault / VIDEO_INDEX, ordered_videos)
    _write_jsonl(vault / CHANNEL_INDEX, ordered_channels)
    _write_jsonl(vault / BATCH_INDEX, ordered_batches)
    (memory_root / "video-index.md").write_text(
        _video_index_markdown(ordered_videos),
        encoding="utf-8",
    )
    (memory_root / "channel-index.md").write_text(
        _channel_index_markdown(ordered_channels),
        encoding="utf-8",
    )
    (memory_root / "batch-index.md").write_text(
        _batch_index_markdown(ordered_batches),
        encoding="utf-8",
    )
    (memory_root / "README.md").write_text(_memory_readme(), encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "updated_at": _utc_now(),
        "video_count": len(ordered_videos),
        "channel_count": len(ordered_channels),
        "batch_count": len(ordered_batches),
        "video_index": VIDEO_INDEX.as_posix(),
        "channel_index": CHANNEL_INDEX.as_posix(),
        "batch_index": BATCH_INDEX.as_posix(),
        "lookup_roots": {
            "video_id": "memory/by-video-id/",
            "friendly_title": "memory/by-title/",
            "channel_id": "memory/by-channel-id/",
            "batch_id": "memory/by-batch-id/",
        },
    }
    _write_json(memory_root / "bank-manifest.json", manifest)
    return {
        "videos": len(ordered_videos),
        "channels": len(ordered_channels),
        "batches": len(ordered_batches),
    }


def ensure_video_memory_entry(video_root: Path) -> dict[str, Any]:
    result = _read_json(video_root / "result.json")
    receipt = _read_json(video_root / "receipt.json")
    metadata = result.get("metadata") or {}
    transcript = result.get("transcript") or {}

    title = _clean_text(metadata.get("title")) or str(receipt["video_id"])
    channel = _clean_text(metadata.get("channel")) or "Unknown channel"
    channel_id = _clean_text(metadata.get("channel_id"))
    published_at, published_date = _publication(metadata)
    duration_seconds, duration_source = _duration(metadata, transcript)
    duration_readable = _format_duration(duration_seconds)
    video_id = str(receipt["video_id"])
    friendly_stem = _friendly_video_stem(
        published_date=published_date,
        channel=channel,
        title=title,
        video_id=video_id,
    )

    entry = {
        "schema_version": "1.0",
        "memory_type": "youtube_video",
        "memory_key": f"youtube:{video_id}",
        "video_id": video_id,
        "canonical_url": receipt.get("canonical_url"),
        "title": title,
        "channel": channel,
        "channel_id": channel_id,
        "published_at": published_at,
        "published_date": published_date,
        "duration_seconds": duration_seconds,
        "duration_readable": duration_readable,
        "duration_source": duration_source,
        "fetched_at": receipt.get("fetched_at"),
        "transcript_status": receipt.get("transcript_status"),
        "transcript_coverage_status": receipt.get("transcript_coverage_status"),
        "transcript_source": receipt.get("transcript_source"),
        "segment_count": receipt.get("segment_count", 0),
        "comments_status": receipt.get("comments_status"),
        "comments_coverage_status": receipt.get("comments_coverage_status"),
        "comment_count": receipt.get("comment_count", 0),
        "stable_result_path": f"videos/{video_id}/latest/",
        "reader_manifest_path": f"videos/{video_id}/latest/reader-manifest.json",
        "receipt_path": f"videos/{video_id}/latest/receipt.json",
        "friendly_name": friendly_stem,
        "suggested_download_folder": f"{friendly_stem}__aitube-memory",
        "suggested_archive_name": f"{friendly_stem}__aitube-memory.zip",
        "lookup_paths": {
            "video_id": f"memory/by-video-id/{video_id}.json",
            "friendly_title": f"memory/by-title/{friendly_stem}.json",
        },
    }

    _write_json(video_root / "memory-entry.json", entry)
    (video_root / "memory-entry.md").write_text(
        _video_entry_markdown(entry),
        encoding="utf-8",
    )
    (video_root / "download-name.txt").write_text(
        str(entry["suggested_download_folder"]) + "\n",
        encoding="utf-8",
    )
    return entry


def _write_video_pointers(
    vault: Path,
    entry: dict[str, Any],
    previous: dict[str, Any] | None,
) -> None:
    video_id = str(entry["video_id"])
    memory_root = vault / "memory"
    _write_json(memory_root / "by-video-id" / f"{video_id}.json", entry)

    new_pointer = memory_root / "by-title" / f"{entry['friendly_name']}.json"
    if previous:
        previous_name = str(previous.get("friendly_name") or "")
        if previous_name and previous_name != entry["friendly_name"]:
            old_pointer = memory_root / "by-title" / f"{previous_name}.json"
            old_pointer.unlink(missing_ok=True)

    pointer = {
        "schema_version": "1.0",
        "memory_key": entry["memory_key"],
        "video_id": video_id,
        "title": entry["title"],
        "channel": entry["channel"],
        "published_date": entry["published_date"],
        "duration_readable": entry["duration_readable"],
        "stable_result_path": entry["stable_result_path"],
        "memory_entry_path": entry["lookup_paths"]["video_id"],
    }
    _write_json(new_pointer, pointer)


def _channel_memory_entry(channel_root: Path) -> dict[str, Any]:
    receipt = _read_json(channel_root / "channel-receipt.json")
    catalog_path = channel_root / "channel-catalog.json"
    catalog = _read_json(catalog_path) if catalog_path.is_file() else {}
    channel = catalog.get("channel") or {}
    videos = catalog.get("videos") or []
    channel_id = str(receipt["channel_id"])
    title = _clean_text(receipt.get("channel_title")) or channel_id
    newest = videos[0].get("published_date") if videos else None
    oldest = videos[-1].get("published_date") if videos else None
    return {
        "schema_version": "1.0",
        "memory_type": "youtube_channel_catalog",
        "memory_key": f"youtube-channel:{channel_id}",
        "channel_id": channel_id,
        "channel_title": title,
        "channel_url": channel.get("channel_url"),
        "fetched_at": receipt.get("fetched_at"),
        "status": receipt.get("status"),
        "video_count": receipt.get("video_count", 0),
        "reported_video_count": channel.get("reported_video_count"),
        "newest_selected_publication_date": newest,
        "oldest_selected_publication_date": oldest,
        "catalog_exhausted": receipt.get("catalog_exhausted"),
        "next_start_index": receipt.get("next_start_index"),
        "stable_result_path": f"channels/{channel_id}/latest/",
        "catalog_path": f"channels/{channel_id}/latest/channel-catalog.json",
        "markdown_path": f"channels/{channel_id}/latest/channel-videos.md",
        "jsonl_path": f"channels/{channel_id}/latest/channel-videos.jsonl",
    }


def _batch_memory_entry(batch_root: Path) -> dict[str, Any]:
    receipt = _read_json(batch_root / "batch-receipt.json")
    batch_id = str(receipt["batch_id"])
    request = receipt.get("request") or {}
    return {
        "schema_version": "1.0",
        "memory_type": "youtube_research_batch",
        "memory_key": f"youtube-batch:{batch_id}",
        "batch_id": batch_id,
        "status": receipt.get("status"),
        "started_at": receipt.get("started_at"),
        "completed_at": receipt.get("completed_at"),
        "duration_seconds": receipt.get("duration_seconds"),
        "video_count": receipt.get("resolved_video_count", 0),
        "channel_count": len(receipt.get("channel_catalogs") or []),
        "proven_count": receipt.get("proven_count", 0),
        "partial_count": receipt.get("partial_count", 0),
        "failed_count": receipt.get("failed_count", 0),
        "request_modes": {
            "direct_videos": len(request.get("video_urls") or []),
            "playlists": len(request.get("playlist_urls") or []),
            "channels": len(request.get("channel_urls") or []),
        },
        "stable_result_path": f"batches/{batch_id}/latest/",
        "receipt_path": f"batches/{batch_id}/latest/batch-receipt.json",
        "reader_manifest_path": (
            f"batches/{batch_id}/latest/batch-reader-manifest.json"
        ),
    }


def _publication(metadata: dict[str, Any]) -> tuple[str | None, str | None]:
    published = metadata.get("published_at") or metadata.get("publishedAt")
    if published:
        text = str(published).strip()
        return text, text[:10] if len(text) >= 10 else None

    upload_date = str(metadata.get("upload_date") or "").strip()
    if re.fullmatch(r"\d{8}", upload_date):
        date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        return date, date

    timestamp = metadata.get("timestamp") or metadata.get("release_timestamp")
    if isinstance(timestamp, (int, float)):
        published_at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        return published_at, published_at[:10]
    return None, None


def _duration(
    metadata: dict[str, Any],
    transcript: dict[str, Any],
) -> tuple[int | None, str | None]:
    for key in ("duration_seconds", "duration"):
        value = metadata.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return int(round(value)), f"metadata.{key}"

    segments = transcript.get("segments") if isinstance(transcript, dict) else None
    if isinstance(segments, list) and segments:
        end = max(
            float(segment.get("start") or 0) + float(segment.get("duration") or 0)
            for segment in segments
            if isinstance(segment, dict)
        )
        return int(round(end)), "transcript_end_estimate"
    return None, None


def _friendly_video_stem(
    *,
    published_date: str | None,
    channel: str,
    title: str,
    video_id: str,
) -> str:
    date = published_date or "undated"
    channel_slug = _safe_component(channel, 36) or "unknown-channel"
    title_slug = _safe_component(title, 80) or "untitled"
    return f"{date}__{channel_slug}__{title_slug}__{video_id}"


def _safe_component(value: str, limit: int) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    return slug[:limit].rstrip("-")


def _format_duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _video_entry_markdown(entry: dict[str, Any]) -> str:
    lines = [
        f"# {entry['title']}",
        "",
        f"- Memory key: `{entry['memory_key']}`",
        f"- Video ID: `{entry['video_id']}`",
        f"- Channel: {entry['channel']}",
        f"- Published: {entry['published_date'] or 'unknown'}",
        f"- Duration: {entry['duration_readable'] or 'unknown'}",
        f"- Fetched: {entry['fetched_at'] or 'unknown'}",
        f"- Transcript: `{entry['transcript_status']}` / "
        f"`{entry['transcript_coverage_status']}`",
        f"- Comments: `{entry['comments_status']}` / "
        f"`{entry['comments_coverage_status']}`",
        f"- Stable result: `{entry['stable_result_path']}`",
        f"- Reader manifest: `{entry['reader_manifest_path']}`",
        f"- Logical download name: `{entry['suggested_download_folder']}`",
        "",
        "Use the stable video-ID path for automation. Use the logical name for downloaded "
        "folders or archives.",
    ]
    return "\n".join(lines) + "\n"


def _video_index_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# AITube video memory index",
        "",
        "Stable lookup: `memory/by-video-id/<video-id>.json`",
        "",
        "| Published | Duration | Channel | Title | Video ID | Transcript | Comments |",
        "|---|---:|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(entry.get("published_date") or "unknown"),
                    _md(entry.get("duration_readable") or "unknown"),
                    _md(entry.get("channel") or "unknown"),
                    _md(entry.get("title") or "untitled"),
                    f"`{entry['video_id']}`",
                    f"`{entry.get('transcript_coverage_status')}`",
                    f"`{entry.get('comments_coverage_status')}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _channel_index_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# AITube channel memory index",
        "",
        "| Fetched | Channel | Selected videos | Status | Channel ID |",
        "|---|---|---:|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(str(entry.get("fetched_at") or "unknown")[:10]),
                    _md(entry.get("channel_title") or "unknown"),
                    str(entry.get("video_count") or 0),
                    f"`{entry.get('status')}`",
                    f"`{entry['channel_id']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _batch_index_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# AITube batch memory index",
        "",
        "| Completed | Batch ID | Status | Videos | Channels | Failed |",
        "|---|---|---|---:|---:|---:|",
    ]
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(str(entry.get("completed_at") or "unknown")[:19]),
                    f"`{entry['batch_id']}`",
                    f"`{entry.get('status')}`",
                    str(entry.get("video_count") or 0),
                    str(entry.get("channel_count") or 0),
                    str(entry.get("failed_count") or 0),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _memory_readme() -> str:
    return """# Private AITube memory bank

This directory is the compact lookup layer for permanent YouTube research stored on the
private `aitube-results` branch.

## Lookup order

1. Known video ID: `by-video-id/<video-id>.json`
2. Title, channel, or date: `video-index.jsonl` or `video-index.md`
3. Channel catalog: `by-channel-id/<channel-id>.json`
4. Batch or playlist run: `by-batch-id/<batch-id>.json`
5. Open only the referenced result receipt, reader manifest, and required chunks.

The complete transcript, description, and comments remain under the stable
`videos/<video-id>/latest/` path. Human-readable pointer filenames under `by-title/` use:

`YYYY-MM-DD__channel__title__VIDEO_ID.json`

Do not store full transcripts or API secrets in ChatGPT memory. Store only the repository,
branch, lookup paths, and rules for consulting this external memory bank.
"""


def _load_index(path: Path, key: str) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        result[str(item[key])] = item
    return result


def _write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
        for item in entries
    )
    path.write_text(content, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or update the private AITube GitHub memory bank."
    )
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--batch-receipt", type=Path)
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--channel-id", action="append", default=[])
    parser.add_argument("--rebuild-all", action="store_true")
    args = parser.parse_args()

    counts = update_memory_bank(
        args.vault,
        batch_receipt=args.batch_receipt,
        video_ids=args.video_id,
        channel_ids=args.channel_id,
        rebuild_all=args.rebuild_all,
    )
    print(f"MEMORY_VIDEO_COUNT={counts['videos']}")
    print(f"MEMORY_CHANNEL_COUNT={counts['channels']}")
    print(f"MEMORY_BATCH_COUNT={counts['batches']}")
    print("MEMORY_BANK_STATUS=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
