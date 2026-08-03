from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .storage_common import (
    DURABLE_BRANCH,
    clean_text,
    copy_file,
    copy_immutable_tree,
    copy_tree,
    duration_seconds,
    iso,
    parse_datetime,
    published_at,
    read_json,
    replace_tree,
    safe_component,
    snapshot_key,
    tree_sha256,
    trust_record,
    write_json,
    write_jsonl,
)

DEFAULT_RETENTION_DAYS = 30
DEFAULT_REFRESH_DAYS = 25


def publish_video_overlay(
    *,
    source: Path,
    root: Path,
    video_id: str,
    durable_pointer: dict[str, Any],
    fetched_at: Any,
    comments_requested: int,
    authorization_mode: str,
    refresh_days: int,
    retention_days: int,
) -> dict[str, Any]:
    receipt = read_json(source / "receipt.json")
    result = read_json(source / "result.json") if (source / "result.json").is_file() else {}
    metadata = result.get("metadata") or {}
    fetched = parse_datetime(fetched_at)
    key = str(durable_pointer["snapshot_key"])
    container = root / "videos" / video_id
    overlay = container / "overlays" / key
    retention = api_retention(
        fetched,
        authorization_mode=authorization_mode,
        refresh_days=refresh_days,
        retention_days=retention_days,
        data_classes=_video_data_classes(
            comments_requested, int(receipt.get("comment_count") or 0)
        ),
    )

    with tempfile.TemporaryDirectory(prefix="aitube-overlay-") as work:
        staging = Path(work)
        for name in ("description.md", "comments.md", "comments-manifest.json"):
            copy_file(source / name, staging / name, required=False)
        copy_tree(source / "comment-chunks", staging / "comment-chunks")
        write_json(
            staging / "api-result.json",
            {
                "schema_version": "3.0",
                "video_id": video_id,
                "metadata": metadata,
                "comments": result.get("comments") or {},
            },
        )
        overlay_metadata = {
            "schema_version": "3.0",
            "storage_class": "VOLATILE_YOUTUBE_API_OVERLAY",
            "kind": "video",
            "identity": video_id,
            "snapshot_key": key,
            "overlay_path": f"videos/{video_id}/overlays/{key}/",
            "durable_branch": DURABLE_BRANCH,
            "durable_snapshot_path": durable_pointer["snapshot_path"],
            "fetched_at": iso(fetched),
            "title": clean_text(metadata.get("title")),
            "channel": clean_text(metadata.get("channel")),
            "channel_id": clean_text(metadata.get("channel_id")),
            "published_at": published_at(metadata),
            "duration_seconds": duration_seconds(
                metadata, result.get("transcript") or {}
            ),
            "comments_requested": comments_requested,
            "comment_count": int(receipt.get("comment_count") or 0),
            "comments_status": receipt.get("comments_status"),
            "comments_coverage_status": receipt.get("comments_coverage_status"),
            "retention": retention,
            "trust": trust_record(),
        }
        write_json(staging / "overlay-metadata.json", overlay_metadata)
        digest = tree_sha256(staging)
        overlay_metadata["overlay_sha256"] = digest
        write_json(staging / "overlay-metadata.json", overlay_metadata)
        copy_immutable_tree(
            staging,
            overlay,
            digest=digest,
            metadata_name="overlay-metadata.json",
            digest_field="overlay_sha256",
        )

    replace_tree(overlay, container / "current")
    pointer = overlay_pointer(read_json(overlay / "overlay-metadata.json"))
    write_json(container / "pointers" / "latest.json", pointer)
    write_video_overlay_best_pointers(container)
    write_json(root / "memory" / "by-video-id" / f"{video_id}.json", pointer)
    return pointer


def publish_channel_overlay(
    *,
    source: Path,
    root: Path,
    channel_id: str,
    fetched_at: Any,
    authorization_mode: str,
    refresh_days: int,
    retention_days: int,
) -> dict[str, Any]:
    receipt = read_json(source / "channel-receipt.json")
    fetched = parse_datetime(receipt.get("fetched_at") or fetched_at)
    profile = {
        "video_count": int(receipt.get("video_count") or 0),
        "catalog_exhausted": bool(receipt.get("catalog_exhausted")),
        "next_start_index": receipt.get("next_start_index"),
    }
    digest = tree_sha256(source)
    key = snapshot_key(fetched, digest, digest)
    container = root / "channels" / channel_id
    overlay = container / "overlays" / key
    metadata = {
        "schema_version": "3.0",
        "storage_class": "VOLATILE_YOUTUBE_API_OVERLAY",
        "kind": "channel",
        "identity": channel_id,
        "snapshot_key": key,
        "overlay_path": f"channels/{channel_id}/overlays/{key}/",
        "fetched_at": iso(fetched),
        "channel_title": receipt.get("channel_title"),
        **profile,
        "retention": api_retention(
            fetched,
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
            data_classes=[
                "channel_metadata",
                "channel_upload_catalog",
                "video_statistics_snapshot",
            ],
        ),
        "trust": trust_record(),
        "overlay_sha256": digest,
    }
    if not overlay.exists():
        overlay.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, overlay)
        write_json(overlay / "overlay-metadata.json", metadata)
    replace_tree(overlay, container / "current")
    pointer = overlay_pointer(metadata)
    write_json(container / "pointers" / "latest.json", pointer)
    write_channel_best_pointers(container)
    write_json(root / "memory" / "by-channel-id" / f"{channel_id}.json", pointer)
    return pointer


def publish_batch_overlay(
    *,
    source: Path,
    root: Path,
    batch_id: str,
    durable_batch: dict[str, Any],
    fetched_at: Any,
    authorization_mode: str,
    refresh_days: int,
    retention_days: int,
) -> dict[str, Any]:
    fetched = parse_datetime(fetched_at)
    key = str(durable_batch["snapshot_key"])
    container = root / "batches" / batch_id
    overlay = container / "overlays" / key
    digest = tree_sha256(source)
    metadata = {
        "schema_version": "3.0",
        "storage_class": "VOLATILE_YOUTUBE_API_OVERLAY",
        "kind": "batch",
        "identity": batch_id,
        "snapshot_key": key,
        "overlay_path": f"batches/{batch_id}/overlays/{key}/",
        "durable_branch": DURABLE_BRANCH,
        "durable_snapshot_path": durable_batch["snapshot_path"],
        "fetched_at": iso(fetched),
        "retention": api_retention(
            fetched,
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
            data_classes=["batch_api_result_references"],
        ),
        "trust": trust_record(),
        "overlay_sha256": digest,
    }
    if not overlay.exists():
        overlay.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, overlay)
        write_json(overlay / "overlay-metadata.json", metadata)
    replace_tree(overlay, container / "current")
    pointer = overlay_pointer(metadata)
    write_json(container / "pointers" / "latest.json", pointer)
    write_json(
        root / "memory" / "by-batch-id" / f"{safe_component(batch_id, 100)}.json",
        pointer,
    )
    return pointer


def purge_expired_overlays(
    root: Path, *, now: datetime | None = None
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    removed: list[str] = []
    for metadata_path in sorted(root.glob("*/*/overlays/*/overlay-metadata.json")):
        metadata = read_json(metadata_path)
        deadline = (metadata.get("retention") or {}).get("delete_or_refresh_by")
        if not deadline or parse_datetime(deadline) > current:
            continue
        overlay = metadata_path.parent
        removed.append(overlay.relative_to(root).as_posix() + "/")
        shutil.rmtree(overlay)
    repair_current_and_pointers(root)
    return {"removed_count": len(removed), "removed_paths": removed}


def repair_current_and_pointers(root: Path) -> None:
    memory_roots = {
        "videos": "by-video-id",
        "channels": "by-channel-id",
        "batches": "by-batch-id",
    }
    for kind in ("videos", "channels", "batches"):
        base = root / kind
        if not base.is_dir():
            continue
        for container in base.iterdir():
            if not container.is_dir():
                continue
            identity = container.name
            memory_name = (
                f"{safe_component(identity, 100)}.json"
                if kind == "batches"
                else f"{identity}.json"
            )
            memory_path = root / "memory" / memory_roots[kind] / memory_name
            metadata_files = sorted(
                (container / "overlays").glob("*/overlay-metadata.json")
            )
            if not metadata_files:
                shutil.rmtree(container / "current", ignore_errors=True)
                shutil.rmtree(container / "pointers", ignore_errors=True)
                memory_path.unlink(missing_ok=True)
                continue
            metadata = [read_json(path) for path in metadata_files]
            latest = max(metadata, key=lambda item: str(item.get("fetched_at") or ""))
            latest_path = container / "overlays" / str(latest["snapshot_key"])
            replace_tree(latest_path, container / "current")
            pointer = overlay_pointer(latest)
            write_json(container / "pointers" / "latest.json", pointer)
            write_json(memory_path, pointer)
            if kind == "videos":
                write_video_overlay_best_pointers(container)
            elif kind == "channels":
                write_channel_best_pointers(container)


def write_video_overlay_best_pointers(container: Path) -> None:
    candidates = [
        read_json(path)
        for path in (container / "overlays").glob("*/overlay-metadata.json")
    ]
    comments = [
        item
        for item in candidates
        if item.get("comments_status") == "PROVEN"
        and item.get("comments_coverage_status") == "PROVEN"
    ]
    if not comments:
        return
    chosen = max(
        comments,
        key=lambda item: (
            int(item.get("comment_count") or 0),
            str(item.get("fetched_at") or ""),
        ),
    )
    pointer = overlay_pointer(chosen)
    write_json(container / "pointers" / "best-comments.json", pointer)
    write_json(container / "pointers" / "best-complete.json", pointer)


def write_channel_best_pointers(container: Path) -> None:
    candidates = [
        read_json(path)
        for path in (container / "overlays").glob("*/overlay-metadata.json")
    ]
    if not candidates:
        return
    widest = max(
        candidates,
        key=lambda item: (
            bool(item.get("catalog_exhausted")),
            int(item.get("video_count") or 0),
            str(item.get("fetched_at") or ""),
        ),
    )
    write_json(container / "pointers" / "widest-catalog.json", overlay_pointer(widest))
    complete = [item for item in candidates if item.get("catalog_exhausted")]
    if complete:
        newest_complete = max(complete, key=lambda item: str(item.get("fetched_at") or ""))
        write_json(
            container / "pointers" / "freshest-complete.json",
            overlay_pointer(newest_complete),
        )


def rebuild_volatile_indexes(
    root: Path, *, now: datetime | None = None
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    records = []
    for path in root.glob("*/*/overlays/*/overlay-metadata.json"):
        item = read_json(path)
        item["retention"] = evaluate_retention(item.get("retention") or {}, current)
        write_json(path, item)
        records.append(item)

    repair_current_and_pointers(root)

    by_title = root / "memory" / "by-title"
    shutil.rmtree(by_title, ignore_errors=True)
    video_entries = []
    for path in sorted((root / "memory" / "by-video-id").glob("*.json")):
        entry = read_json(path)
        video_entries.append(entry)
        write_json(by_title / f"{_friendly_stem(entry)}.json", entry)

    channel_entries = [
        read_json(path)
        for path in sorted((root / "memory" / "by-channel-id").glob("*.json"))
    ]
    batch_entries = [
        read_json(path)
        for path in sorted((root / "memory" / "by-batch-id").glob("*.json"))
    ]
    write_jsonl(root / "memory" / "video-index.jsonl", video_entries)
    write_jsonl(root / "memory" / "channel-index.jsonl", channel_entries)
    write_jsonl(root / "memory" / "batch-index.jsonl", batch_entries)

    deadlines = [
        item["retention"].get("delete_or_refresh_by")
        for item in records
        if item["retention"].get("delete_or_refresh_by")
    ]
    write_json(
        root / "retention" / "manifest.json",
        {
            "schema_version": "3.0",
            "updated_at": iso(current),
            "record_count": len(records),
            "next_delete_or_refresh_by": min(deadlines) if deadlines else None,
            "status_counts": _status_counts(records),
            "history_model": "SINGLE_REACHABLE_COMMIT_REWRITE",
            "physical_host_garbage_collection": "NOT_INDEPENDENTLY_PROVEN",
        },
    )
    write_json(
        root / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "VOLATILE_API_MEMORY_INDEX",
            "updated_at": iso(current),
            "video_count": len(video_entries),
            "channel_count": len(channel_entries),
            "batch_count": len(batch_entries),
            "lookup_roots": {
                "video_id": "memory/by-video-id/",
                "friendly_title": "memory/by-title/",
                "channel_id": "memory/by-channel-id/",
                "batch_id": "memory/by-batch-id/",
            },
            "durable_branch": DURABLE_BRANCH,
        },
    )
    return {
        "videos": len(video_entries),
        "channels": len(channel_entries),
        "batches": len(batch_entries),
        "records": len(records),
    }


def evaluate_retention(
    retention: dict[str, Any], now: datetime
) -> dict[str, Any]:
    updated = dict(retention)
    refresh_due = updated.get("refresh_due_at")
    delete_by = updated.get("delete_or_refresh_by")
    if delete_by and parse_datetime(delete_by) <= now:
        updated["status"] = "EXPIRED"
        updated["action"] = "PURGE_REQUIRED"
    elif refresh_due and parse_datetime(refresh_due) <= now:
        updated["status"] = "REFRESH_DUE"
        updated["action"] = "REFRESH_OR_DELETE"
    else:
        updated["status"] = "CURRENT"
    return updated


def api_retention(
    fetched: datetime,
    *,
    authorization_mode: str,
    refresh_days: int,
    retention_days: int,
    data_classes: list[str],
) -> dict[str, Any]:
    return {
        "policy_version": "youtube-api-non-authorized-v2",
        "data_origin": "youtube-data-api-v3",
        "authorization_mode": authorization_mode,
        "data_classes": data_classes,
        "fetched_at": iso(fetched),
        "refresh_due_at": iso(fetched + timedelta(days=refresh_days)),
        "delete_or_refresh_by": iso(fetched + timedelta(days=retention_days)),
        "status": "CURRENT",
        "action": "REFRESH_OR_DELETE",
    }


def overlay_pointer(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "storage_class",
        "kind",
        "identity",
        "snapshot_key",
        "overlay_path",
        "durable_branch",
        "durable_snapshot_path",
        "fetched_at",
        "title",
        "channel",
        "channel_id",
        "published_at",
        "duration_seconds",
        "comment_count",
        "comments_requested",
        "comments_status",
        "comments_coverage_status",
        "channel_title",
        "video_count",
        "catalog_exhausted",
        "next_start_index",
        "retention",
        "trust",
    )
    return {key: metadata.get(key) for key in keys if key in metadata}


def _video_data_classes(requested: int, retrieved: int) -> list[str]:
    classes = ["video_metadata", "video_description"]
    if requested > 0 or retrieved > 0:
        classes.append("top_level_comments")
    return classes


def _friendly_stem(entry: dict[str, Any]) -> str:
    date = str(entry.get("published_at") or "undated")[:10]
    channel = safe_component(str(entry.get("channel") or "unknown-channel"), 36)
    title = safe_component(str(entry.get("title") or "untitled"), 80)
    return f"{date}__{channel}__{title}__{entry['identity']}"


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        status = str((item.get("retention") or {}).get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts
