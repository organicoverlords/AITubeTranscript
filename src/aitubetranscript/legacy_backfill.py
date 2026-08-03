from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .memory_bank import update_memory_bank
from .memory_preference import promote_preferred_video_entries
from .snapshot_store import (
    DEFAULT_REFRESH_DAYS,
    DEFAULT_RETENTION_DAYS,
    _api_retention,
    _internal_retention,
    _publish_bundle,
    _write_retention_record,
    _write_video_best_pointers,
    rebuild_retention_manifest,
)


def backfill_legacy_latest(
    vault: Path,
    *,
    authorization_mode: str = "api_key_non_authorized",
    retention_days: int = DEFAULT_RETENTION_DAYS,
    refresh_days: int = DEFAULT_REFRESH_DAYS,
) -> dict[str, int]:
    """Convert pre-snapshot latest bundles into one immutable snapshot each.

    This intentionally migrates only the currently materialized ``latest/`` bundle.
    Historical variants that exist solely in Git history require a separate recovery pass.
    """

    vault = vault.resolve()
    if not 0 < refresh_days <= retention_days:
        raise ValueError("refresh_days must be positive and <= retention_days")

    counts = {"videos": 0, "channels": 0, "batches": 0, "skipped": 0}
    migrated_video_ids: list[str] = []

    for latest in sorted((vault / "videos").glob("*/latest")):
        receipt_path = latest / "receipt.json"
        if not receipt_path.is_file():
            continue
        if (latest / "snapshot-metadata.json").is_file():
            counts["skipped"] += 1
            continue

        receipt = _read_json(receipt_path)
        video_id = str(receipt.get("video_id") or latest.parent.name)
        comment_count = int(receipt.get("comment_count") or 0)
        transcript_source = str(receipt.get("transcript_source") or "")
        language = _infer_language(transcript_source)
        comments_proven = (
            receipt.get("comments_status") == "PROVEN"
            and receipt.get("comments_coverage_status") == "PROVEN"
        )
        requested_comments = comment_count if comments_proven else 0
        data_classes = ["video_metadata", "video_description"]
        if comment_count > 0:
            data_classes.append("top_level_comments")

        published = _publish_bundle(
            source=latest,
            container=latest.parent,
            kind="video",
            identity=video_id,
            fetched_at=receipt.get("fetched_at"),
            profile={
                "languages": language,
                "comments_requested": requested_comments,
                "whisper": "whisper" in transcript_source.lower(),
                "transcript_source": transcript_source or None,
                "legacy_inferred": True,
            },
            retention=_api_retention(
                fetched_at=receipt.get("fetched_at"),
                authorization_mode=authorization_mode,
                refresh_days=refresh_days,
                retention_days=retention_days,
                data_classes=data_classes,
            ),
            evidence={
                "transcript_status": receipt.get("transcript_status"),
                "transcript_coverage_status": receipt.get(
                    "transcript_coverage_status"
                ),
                "comments_status": receipt.get("comments_status"),
                "comments_coverage_status": receipt.get(
                    "comments_coverage_status"
                ),
                "segment_count": int(receipt.get("segment_count") or 0),
                "comment_count": comment_count,
            },
        )
        _write_video_best_pointers(vault, video_id)
        _write_retention_record(vault, "videos", video_id, published)
        migrated_video_ids.append(video_id)
        counts["videos"] += 1

    for latest in sorted((vault / "channels").glob("*/latest")):
        receipt_path = latest / "channel-receipt.json"
        if not receipt_path.is_file():
            continue
        if (latest / "snapshot-metadata.json").is_file():
            counts["skipped"] += 1
            continue

        receipt = _read_json(receipt_path)
        channel_id = str(receipt.get("channel_id") or latest.parent.name)
        published = _publish_bundle(
            source=latest,
            container=latest.parent,
            kind="channel",
            identity=channel_id,
            fetched_at=receipt.get("fetched_at"),
            profile={
                "video_count": int(receipt.get("video_count") or 0),
                "catalog_exhausted": receipt.get("catalog_exhausted"),
                "next_start_index": receipt.get("next_start_index"),
                "legacy_inferred": True,
            },
            retention=_api_retention(
                fetched_at=receipt.get("fetched_at"),
                authorization_mode=authorization_mode,
                refresh_days=refresh_days,
                retention_days=retention_days,
                data_classes=[
                    "channel_metadata",
                    "channel_upload_catalog",
                    "video_statistics_snapshot",
                ],
            ),
        )
        _write_retention_record(vault, "channels", channel_id, published)
        counts["channels"] += 1

    for latest in sorted((vault / "batches").glob("*/latest")):
        receipt_path = latest / "batch-receipt.json"
        if not receipt_path.is_file():
            continue
        if (latest / "snapshot-metadata.json").is_file():
            counts["skipped"] += 1
            continue

        receipt = _read_json(receipt_path)
        batch_id = str(receipt.get("batch_id") or latest.parent.name)
        published = _publish_bundle(
            source=latest,
            container=latest.parent,
            kind="batch",
            identity=batch_id,
            fetched_at=receipt.get("completed_at") or receipt.get("started_at"),
            profile={
                "request_sha256": receipt.get("request_sha256"),
                "legacy_inferred": True,
            },
            retention=_internal_retention(
                receipt.get("completed_at") or receipt.get("started_at")
            ),
        )
        _write_retention_record(vault, "batches", batch_id, published)
        counts["batches"] += 1

    update_memory_bank(vault, rebuild_all=True)
    all_video_ids = [
        path.parent.parent.name
        for path in (vault / "videos").glob("*/pointers/best.json")
    ]
    promote_preferred_video_entries(vault, all_video_ids)
    rebuild_retention_manifest(vault)

    counts["preferred_videos"] = len(all_video_ids)
    counts["migrated_video_ids"] = len(migrated_video_ids)
    return counts


def _infer_language(transcript_source: str) -> str:
    text = transcript_source.strip()
    if ":" in text:
        candidate = text.rsplit(":", 1)[-1].strip()
        if candidate:
            return candidate
    return "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill legacy latest-only AITube bundles into immutable snapshots."
    )
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--authorization-mode", default="api_key_non_authorized")
    parser.add_argument("--refresh-days", type=int, default=DEFAULT_REFRESH_DAYS)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    counts = backfill_legacy_latest(
        args.vault,
        authorization_mode=args.authorization_mode,
        retention_days=args.retention_days,
        refresh_days=args.refresh_days,
    )
    print(f"BACKFILL_VIDEOS={counts['videos']}")
    print(f"BACKFILL_CHANNELS={counts['channels']}")
    print(f"BACKFILL_BATCHES={counts['batches']}")
    print(f"BACKFILL_SKIPPED={counts['skipped']}")
    print(f"PREFERRED_VIDEO_COUNT={counts['preferred_videos']}")
    print("LEGACY_SNAPSHOT_BACKFILL=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
