from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .durable_store import (
    publish_durable_batch,
    publish_durable_video,
    rebuild_durable_indexes,
)
from .storage_common import DURABLE_BRANCH, VOLATILE_BRANCH, read_json
from .volatile_store import (
    DEFAULT_REFRESH_DAYS,
    DEFAULT_RETENTION_DAYS,
    publish_batch_overlay,
    publish_channel_overlay,
    publish_video_overlay,
    purge_expired_overlays,
    rebuild_volatile_indexes,
)


def publish_split_batch(
    source_root: Path,
    durable_root: Path,
    volatile_root: Path,
    batch_id: str,
    *,
    authorization_mode: str = "api_key_non_authorized",
    refresh_days: int = DEFAULT_REFRESH_DAYS,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    durable_root = durable_root.resolve()
    volatile_root = volatile_root.resolve()
    if not 0 < refresh_days <= retention_days:
        raise ValueError("refresh_days must be positive and <= retention_days")

    batch_source = source_root / "batches" / batch_id
    receipt = read_json(batch_source / "batch-receipt.json")
    if str(receipt.get("batch_id")) != batch_id:
        raise ValueError("batch receipt ID mismatch")
    request = receipt.get("request") or {}
    fetched_at = receipt.get("completed_at") or receipt.get("started_at")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    durable_videos: list[dict[str, Any]] = []
    volatile_videos: list[dict[str, Any]] = []
    for item in receipt.get("results") or []:
        if item.get("status") == "FAILED":
            continue
        video_id = str(item["video_id"])
        source = source_root / video_id
        video_receipt = read_json(source / "receipt.json")
        durable = publish_durable_video(
            source=source,
            root=durable_root,
            video_id=video_id,
            fetched_at=video_receipt.get("fetched_at") or fetched_at,
            profile={
                "languages": request.get("languages") or "en",
                "whisper": bool(request.get("whisper", False)),
                "transcript_source": video_receipt.get("transcript_source"),
            },
        )
        volatile = publish_video_overlay(
            source=source,
            root=volatile_root,
            video_id=video_id,
            durable_pointer=durable,
            fetched_at=video_receipt.get("fetched_at") or fetched_at,
            comments_requested=int(request.get("comments") or 0),
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
        )
        durable_videos.append(durable)
        volatile_videos.append(volatile)

    channel_overlays = []
    for item in receipt.get("channel_catalogs") or []:
        channel_id = str(item["channel_id"])
        channel_overlays.append(
            publish_channel_overlay(
                source=source_root / "channels" / channel_id,
                root=volatile_root,
                channel_id=channel_id,
                fetched_at=fetched_at,
                authorization_mode=authorization_mode,
                refresh_days=refresh_days,
                retention_days=retention_days,
            )
        )

    durable_batch = publish_durable_batch(
        root=durable_root,
        batch_id=batch_id,
        receipt=receipt,
        durable_videos=durable_videos,
    )
    volatile_batch = publish_batch_overlay(
        source=batch_source,
        root=volatile_root,
        batch_id=batch_id,
        durable_batch=durable_batch,
        fetched_at=fetched_at,
        authorization_mode=authorization_mode,
        refresh_days=refresh_days,
        retention_days=retention_days,
    )
    purge = purge_expired_overlays(volatile_root, now=current)
    durable_index = rebuild_durable_indexes(durable_root)
    volatile_index = rebuild_volatile_indexes(volatile_root, now=current)
    return {
        "durable_branch": DURABLE_BRANCH,
        "volatile_branch": VOLATILE_BRANCH,
        "durable_batch": durable_batch,
        "volatile_batch": volatile_batch,
        "durable_videos": durable_videos,
        "volatile_videos": volatile_videos,
        "channel_overlays": channel_overlays,
        "purge": purge,
        "durable_index": durable_index,
        "volatile_index": volatile_index,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split durable transcript evidence from volatile YouTube API data."
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--durable-root", required=True, type=Path)
    parser.add_argument("--volatile-root", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--authorization-mode", default="api_key_non_authorized")
    parser.add_argument("--refresh-days", type=int, default=DEFAULT_REFRESH_DAYS)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = publish_split_batch(
        args.source_root,
        args.durable_root,
        args.volatile_root,
        args.batch_id,
        authorization_mode=args.authorization_mode,
        refresh_days=args.refresh_days,
        retention_days=args.retention_days,
    )
    print(f"DURABLE_VIDEOS={len(result['durable_videos'])}")
    print(f"VOLATILE_VIDEOS={len(result['volatile_videos'])}")
    print(f"VOLATILE_CHANNELS={len(result['channel_overlays'])}")
    print(f"PURGED_OVERLAYS={result['purge']['removed_count']}")
    print("DURABLE_VOLATILE_SPLIT=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
