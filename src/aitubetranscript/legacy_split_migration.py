from __future__ import annotations

import argparse
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .durable_store import (
    publish_durable_batch,
    publish_durable_video,
    rebuild_durable_indexes,
)
from .storage_common import read_json, write_json
from .volatile_store import (
    DEFAULT_REFRESH_DAYS,
    DEFAULT_RETENTION_DAYS,
    publish_batch_overlay,
    publish_channel_overlay,
    publish_video_overlay,
    purge_expired_overlays,
    rebuild_volatile_indexes,
)


def migrate_legacy_results(
    legacy_root: Path,
    durable_root: Path,
    volatile_root: Path,
    *,
    authorization_mode: str = "api_key_non_authorized",
    refresh_days: int = DEFAULT_REFRESH_DAYS,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Migrate currently materialized legacy latest bundles without refetching."""
    legacy_root = legacy_root.resolve()
    durable_root = durable_root.resolve()
    volatile_root = volatile_root.resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    durable_by_video: dict[str, dict[str, Any]] = {}
    volatile_videos = []
    reconstructed_monolithic_transcripts = 0
    for source in sorted((legacy_root / "videos").glob("*/latest")):
        if not (source / "receipt.json").is_file():
            continue
        video_id = source.parent.name
        receipt = read_json(source / "receipt.json")
        if _ensure_legacy_transcript_manifest(source, receipt):
            reconstructed_monolithic_transcripts += 1
        legacy_memory = _legacy_memory_entry(legacy_root, video_id)
        profile = legacy_memory.get("request_profile") or {}
        durable = publish_durable_video(
            source=source,
            root=durable_root,
            video_id=video_id,
            fetched_at=receipt.get("fetched_at"),
            profile={
                "languages": profile.get("languages") or "en",
                "whisper": bool(profile.get("whisper", False)),
                "transcript_source": receipt.get("transcript_source"),
                "legacy_inferred": True,
            },
        )
        comments_requested = int(
            profile.get("comments_requested")
            or receipt.get("comment_count")
            or 0
        )
        volatile = publish_video_overlay(
            source=source,
            root=volatile_root,
            video_id=video_id,
            durable_pointer=durable,
            fetched_at=receipt.get("fetched_at"),
            comments_requested=comments_requested,
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
        )
        durable_by_video[video_id] = durable
        volatile_videos.append(volatile)

    channel_overlays = []
    for source in sorted((legacy_root / "channels").glob("*/latest")):
        if not (source / "channel-receipt.json").is_file():
            continue
        channel_id = source.parent.name
        channel_overlays.append(
            publish_channel_overlay(
                source=source,
                root=volatile_root,
                channel_id=channel_id,
                fetched_at=read_json(source / "channel-receipt.json").get(
                    "fetched_at"
                ),
                authorization_mode=authorization_mode,
                refresh_days=refresh_days,
                retention_days=retention_days,
            )
        )

    durable_batches = []
    volatile_batches = []
    for source in sorted((legacy_root / "batches").glob("*/latest")):
        if not (source / "batch-receipt.json").is_file():
            continue
        batch_id = source.parent.name
        receipt = read_json(source / "batch-receipt.json")
        selected = [
            durable_by_video[str(item["video_id"])]
            for item in receipt.get("results") or []
            if item.get("status") != "FAILED"
            and str(item.get("video_id")) in durable_by_video
        ]
        durable_batch = publish_durable_batch(
            root=durable_root,
            batch_id=batch_id,
            receipt=receipt,
            durable_videos=selected,
        )
        volatile_batch = publish_batch_overlay(
            source=source,
            root=volatile_root,
            batch_id=batch_id,
            durable_batch=durable_batch,
            fetched_at=receipt.get("completed_at") or receipt.get("started_at"),
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
        )
        durable_batches.append(durable_batch)
        volatile_batches.append(volatile_batch)

    purge = purge_expired_overlays(volatile_root, now=current)
    durable_index = rebuild_durable_indexes(durable_root)
    volatile_index = rebuild_volatile_indexes(volatile_root, now=current)
    return {
        "durable_videos": len(durable_by_video),
        "volatile_videos": len(volatile_videos),
        "channels": len(channel_overlays),
        "durable_batches": len(durable_batches),
        "volatile_batches": len(volatile_batches),
        "reconstructed_monolithic_transcripts": (
            reconstructed_monolithic_transcripts
        ),
        "purged_overlays": purge["removed_count"],
        "durable_index": durable_index,
        "volatile_index": volatile_index,
        "migration_scope": "CURRENTLY_MATERIALIZED_LEGACY_LATEST_ONLY",
        "git_history_recovery": "NOT_ATTEMPTED",
    }


def _ensure_legacy_transcript_manifest(
    source: Path, receipt: dict[str, Any]
) -> bool:
    """Normalize proven legacy transcript coverage for durable publication."""
    manifest_path = source / "transcript-manifest.json"
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        manifest_status = str(
            (manifest.get("coverage") or {}).get("status") or ""
        )
        if (
            not receipt.get("transcript_coverage_status")
            and manifest_status == "PROVEN"
        ):
            receipt["transcript_coverage_status"] = "PROVEN"
            write_json(source / "receipt.json", receipt)
        return False

    transcript_path = source / "transcript.md"
    if not transcript_path.is_file():
        raise FileNotFoundError(
            f"legacy transcript has neither manifest nor transcript.md: {source}"
        )
    if receipt.get("transcript_status") != "PROVEN":
        raise ValueError(
            f"legacy monolithic transcript is not proven: {source.parent.name}"
        )
    segment_count = int(receipt.get("segment_count") or 0)
    if segment_count <= 0:
        raise ValueError(
            f"legacy monolithic transcript has no positive segment count: "
            f"{source.parent.name}"
        )

    actual_sha = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
    expected_sha = str(
        (receipt.get("sha256") or {}).get("transcript.md") or ""
    ).strip()
    if not expected_sha:
        raise ValueError(
            f"legacy monolithic transcript has no recorded transcript.md hash: "
            f"{source.parent.name}"
        )
    if actual_sha != expected_sha:
        raise ValueError(
            f"legacy monolithic transcript hash mismatch: {source.parent.name}"
        )

    chunk_relative = Path("chunks/001.md")
    chunk_path = source / chunk_relative
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(transcript_path, chunk_path)
    coverage = {
        "status": "PROVEN",
        "exactly_once": True,
        "missing_indices": [],
        "duplicate_indices": [],
        "unexpected_indices": [],
        "ordered_contiguous": True,
    }
    write_json(
        manifest_path,
        {
            "schema_version": "1.1",
            "video_id": receipt.get("video_id"),
            "status": "PROVEN",
            "segment_count": segment_count,
            "chunks": [
                {
                    "path": chunk_relative.as_posix(),
                    "chunk_number": 1,
                    "first_segment": 1,
                    "last_segment": segment_count,
                    "sha256": actual_sha,
                }
            ],
            "coverage": coverage,
            "legacy_reconstruction": {
                "mode": "VERIFIED_MONOLITHIC_TRANSCRIPT_MD",
                "source_path": "transcript.md",
                "source_sha256": actual_sha,
                "refetched": False,
            },
        },
    )
    reader_path = source / "reader-manifest.json"
    if not reader_path.is_file():
        write_json(
            reader_path,
            {
                "schema_version": "1.1",
                "video_id": receipt.get("video_id"),
                "transcript": {
                    "status": "PROVEN",
                    "segment_count": segment_count,
                    "manifest": "transcript-manifest.json",
                    "chunks": [chunk_relative.as_posix()],
                },
                "parallel_read_groups": [[chunk_relative.as_posix()]],
                "read_order": [chunk_relative.as_posix()],
                "legacy_reconstruction": {
                    "mode": "VERIFIED_MONOLITHIC_TRANSCRIPT_MD",
                    "refetched": False,
                },
            },
        )
    receipt["transcript_coverage_status"] = "PROVEN"
    write_json(source / "receipt.json", receipt)
    return True


def _legacy_memory_entry(root: Path, video_id: str) -> dict[str, Any]:
    path = root / "memory" / "by-video-id" / f"{video_id}.json"
    return read_json(path) if path.is_file() else {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate legacy AITube latest bundles into split storage."
    )
    parser.add_argument("--legacy-root", required=True, type=Path)
    parser.add_argument("--durable-root", required=True, type=Path)
    parser.add_argument("--volatile-root", required=True, type=Path)
    parser.add_argument("--authorization-mode", default="api_key_non_authorized")
    parser.add_argument("--refresh-days", type=int, default=DEFAULT_REFRESH_DAYS)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = migrate_legacy_results(
        args.legacy_root,
        args.durable_root,
        args.volatile_root,
        authorization_mode=args.authorization_mode,
        refresh_days=args.refresh_days,
        retention_days=args.retention_days,
    )
    print(f"MIGRATED_DURABLE_VIDEOS={result['durable_videos']}")
    print(f"MIGRATED_VOLATILE_VIDEOS={result['volatile_videos']}")
    print(f"MIGRATED_CHANNELS={result['channels']}")
    print(f"MIGRATED_BATCHES={result['durable_batches']}")
    print(
        "RECONSTRUCTED_MONOLITHIC_TRANSCRIPTS="
        f"{result['reconstructed_monolithic_transcripts']}"
    )
    print("LEGACY_SPLIT_MIGRATION=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
