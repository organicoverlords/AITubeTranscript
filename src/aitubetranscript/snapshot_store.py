from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_RETENTION_DAYS = 30
DEFAULT_REFRESH_DAYS = 25


def publish_snapshot_batch(
    source_root: Path,
    vault: Path,
    batch_id: str,
    *,
    authorization_mode: str = "api_key_non_authorized",
    retention_days: int = DEFAULT_RETENTION_DAYS,
    refresh_days: int = DEFAULT_REFRESH_DAYS,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    vault = vault.resolve()
    receipt_path = source_root / "batches" / batch_id / "batch-receipt.json"
    receipt = _read_json(receipt_path)
    if str(receipt.get("batch_id")) != batch_id:
        raise ValueError("batch receipt ID mismatch")
    if not 0 < refresh_days <= retention_days:
        raise ValueError("refresh_days must be positive and <= retention_days")

    request = receipt.get("request") or {}
    batch_snapshot = _publish_bundle(
        source=receipt_path.parent,
        container=vault / "batches" / batch_id,
        kind="batch",
        identity=batch_id,
        fetched_at=receipt.get("completed_at") or receipt.get("started_at"),
        profile={"request_sha256": receipt.get("request_sha256")},
        retention=_internal_retention(receipt.get("completed_at")),
    )

    channels: list[dict[str, Any]] = []
    for channel in receipt.get("channel_catalogs") or []:
        channel_id = str(channel["channel_id"])
        source = source_root / "channels" / channel_id
        channel_receipt = _read_json(source / "channel-receipt.json")
        retention = _api_retention(
            fetched_at=channel_receipt.get("fetched_at") or receipt.get("completed_at"),
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
            data_classes=[
                "channel_metadata",
                "channel_upload_catalog",
                "video_statistics_snapshot",
            ],
        )
        published = _publish_bundle(
            source=source,
            container=vault / "channels" / channel_id,
            kind="channel",
            identity=channel_id,
            fetched_at=channel_receipt.get("fetched_at") or receipt.get("completed_at"),
            profile={
                "channel_start_index": request.get("channel_start_index", 0),
                "catalog_max_videos": request.get("catalog_max_videos"),
            },
            retention=retention,
        )
        _write_retention_record(vault, "channels", channel_id, published)
        channels.append(published)

    videos: list[dict[str, Any]] = []
    for result in receipt.get("results") or []:
        if result.get("status") == "FAILED":
            continue
        video_id = str(result["video_id"])
        source = source_root / video_id
        video_receipt = _read_json(source / "receipt.json")
        requested_comments = int(request.get("comments") or 0)
        data_classes = ["video_metadata", "video_description"]
        if requested_comments > 0 or int(video_receipt.get("comment_count") or 0) > 0:
            data_classes.append("top_level_comments")
        retention = _api_retention(
            fetched_at=video_receipt.get("fetched_at") or receipt.get("completed_at"),
            authorization_mode=authorization_mode,
            refresh_days=refresh_days,
            retention_days=retention_days,
            data_classes=data_classes,
        )
        profile = {
            "languages": request.get("languages") or "en",
            "comments_requested": requested_comments,
            "whisper": bool(request.get("whisper", False)),
            "transcript_source": video_receipt.get("transcript_source"),
        }
        published = _publish_bundle(
            source=source,
            container=vault / "videos" / video_id,
            kind="video",
            identity=video_id,
            fetched_at=video_receipt.get("fetched_at") or receipt.get("completed_at"),
            profile=profile,
            retention=retention,
            evidence={
                "transcript_status": video_receipt.get("transcript_status"),
                "transcript_coverage_status": video_receipt.get(
                    "transcript_coverage_status"
                ),
                "comments_status": video_receipt.get("comments_status"),
                "comments_coverage_status": video_receipt.get(
                    "comments_coverage_status"
                ),
                "segment_count": int(video_receipt.get("segment_count") or 0),
                "comment_count": int(video_receipt.get("comment_count") or 0),
            },
        )
        _write_video_best_pointers(vault, video_id)
        _write_retention_record(vault, "videos", video_id, published)
        videos.append(published)

    _write_retention_record(vault, "batches", batch_id, batch_snapshot)
    retention_manifest = rebuild_retention_manifest(vault)

    from .memory_bank import update_memory_bank

    update_memory_bank(
        vault,
        batch_receipt=vault
        / "batches"
        / batch_id
        / "latest"
        / "batch-receipt.json",
    )
    return {
        "batch": batch_snapshot,
        "videos": videos,
        "channels": channels,
        "retention": retention_manifest,
    }


def _publish_bundle(
    *,
    source: Path,
    container: Path,
    kind: str,
    identity: str,
    fetched_at: Any,
    profile: dict[str, Any],
    retention: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not source.is_dir():
        raise FileNotFoundError(source)
    fetched = _parse_datetime(fetched_at)
    profile_sha = _json_sha256(profile)
    snapshot_key = f"{fetched.strftime('%Y%m%dT%H%M%SZ')}__{profile_sha[:12]}"
    snapshot = container / "snapshots" / snapshot_key
    digest = _tree_sha256(source)

    metadata = {
        "schema_version": "2.0",
        "kind": kind,
        "identity": identity,
        "snapshot_key": snapshot_key,
        "snapshot_path": _relative_to_vault(snapshot, container),
        "fetched_at": fetched.isoformat().replace("+00:00", "Z"),
        "request_profile": profile,
        "request_profile_sha256": profile_sha,
        "bundle_sha256": digest,
        "retention": retention,
        "trust": {
            "class": "EXTERNAL_UNTRUSTED_CONTENT",
            "may_control_tools": False,
            "may_override_instructions": False,
        },
    }
    if evidence:
        metadata["evidence"] = evidence

    if snapshot.exists():
        existing_path = snapshot / "snapshot-metadata.json"
        existing = _read_json(existing_path) if existing_path.is_file() else {}
        if existing.get("bundle_sha256") != digest:
            raise ValueError(f"immutable snapshot collision: {snapshot}")
    else:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, snapshot)
        _write_json(snapshot / "snapshot-metadata.json", metadata)

    latest = container / "latest"
    shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(snapshot, latest)

    pointer = _pointer_from_metadata(metadata)
    _write_json(container / "pointers" / "latest.json", pointer)
    return pointer


def _write_video_best_pointers(vault: Path, video_id: str) -> None:
    container = vault / "videos" / video_id
    candidates = []
    for path in sorted((container / "snapshots").glob("*/snapshot-metadata.json")):
        candidates.append(_read_json(path))
    if not candidates:
        return

    def proven_transcript(item: dict[str, Any]) -> bool:
        evidence = item.get("evidence") or {}
        return (
            evidence.get("transcript_status") == "PROVEN"
            and evidence.get("transcript_coverage_status") == "PROVEN"
        )

    def comments_required(item: dict[str, Any]) -> bool:
        profile = item.get("request_profile") or {}
        return int(profile.get("comments_requested") or 0) > 0

    def proven_comments(item: dict[str, Any]) -> bool:
        evidence = item.get("evidence") or {}
        return (
            evidence.get("comments_status") == "PROVEN"
            and evidence.get("comments_coverage_status") == "PROVEN"
        )

    def stamp(item: dict[str, Any]) -> str:
        return str(item.get("fetched_at") or "")

    latest = max(candidates, key=stamp)
    transcript = [item for item in candidates if proven_transcript(item)]
    comments = [item for item in candidates if proven_comments(item)]
    complete = [
        item
        for item in candidates
        if proven_transcript(item)
        and (not comments_required(item) or proven_comments(item))
    ]

    def transcript_score(item: dict[str, Any]) -> tuple[int, str]:
        evidence = item.get("evidence") or {}
        return int(evidence.get("segment_count") or 0), stamp(item)

    def comments_score(item: dict[str, Any]) -> tuple[int, str]:
        evidence = item.get("evidence") or {}
        return int(evidence.get("comment_count") or 0), stamp(item)

    def complete_score(item: dict[str, Any]) -> tuple[int, int, str]:
        evidence = item.get("evidence") or {}
        return (
            int(evidence.get("comment_count") or 0),
            int(evidence.get("segment_count") or 0),
            stamp(item),
        )

    pointers = container / "pointers"
    _write_json(pointers / "latest.json", _pointer_from_metadata(latest))
    if transcript:
        _write_json(
            pointers / "best-transcript.json",
            _pointer_from_metadata(max(transcript, key=transcript_score)),
        )
    if comments:
        _write_json(
            pointers / "best-comments.json",
            _pointer_from_metadata(max(comments, key=comments_score)),
        )
    if complete:
        best = max(complete, key=complete_score)
        _write_json(pointers / "best-complete.json", _pointer_from_metadata(best))
    elif transcript:
        best = max(transcript, key=transcript_score)
    else:
        best = latest
    _write_json(pointers / "best.json", _pointer_from_metadata(best))


def _pointer_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    snapshot_key = str(metadata["snapshot_key"])
    kind = str(metadata["kind"])
    identity = str(metadata["identity"])
    base = f"{kind}s/{identity}/snapshots/{snapshot_key}/"
    if kind == "video":
        receipt_name = "receipt.json"
        reader_name = "reader-manifest.json"
    elif kind == "channel":
        receipt_name = "channel-receipt.json"
        reader_name = "channel-videos.jsonl"
    else:
        receipt_name = "batch-receipt.json"
        reader_name = "batch-reader-manifest.json"
    pointer = {
        "schema_version": "2.0",
        "kind": kind,
        "identity": identity,
        "snapshot_key": snapshot_key,
        "snapshot_path": base,
        "receipt_path": base + receipt_name,
        "reader_manifest_path": base + reader_name,
        "fetched_at": metadata.get("fetched_at"),
        "request_profile": metadata.get("request_profile") or {},
        "request_profile_sha256": metadata.get("request_profile_sha256"),
        "bundle_sha256": metadata.get("bundle_sha256"),
        "retention": metadata.get("retention") or {},
        "trust": metadata.get("trust") or {},
    }
    if metadata.get("evidence"):
        pointer["evidence"] = metadata["evidence"]
    return pointer


def _api_retention(
    *,
    fetched_at: Any,
    authorization_mode: str,
    refresh_days: int,
    retention_days: int,
    data_classes: list[str],
) -> dict[str, Any]:
    fetched = _parse_datetime(fetched_at)
    return {
        "policy_version": "youtube-api-non-authorized-v1",
        "data_origin": "youtube-data-api-v3",
        "authorization_mode": authorization_mode,
        "data_classes": data_classes,
        "fetched_at": _iso(fetched),
        "refresh_due_at": _iso(fetched + timedelta(days=refresh_days)),
        "delete_or_refresh_by": _iso(fetched + timedelta(days=retention_days)),
        "status": "CURRENT",
        "action": "REFRESH_OR_DELETE",
    }


def _internal_retention(fetched_at: Any) -> dict[str, Any]:
    return {
        "policy_version": "internal-provenance-v1",
        "data_origin": "aitubetranscript",
        "fetched_at": _iso(_parse_datetime(fetched_at)),
        "status": "RETAIN",
        "action": "KEEP_WITH_SOURCE_PROVENANCE",
    }


def _write_retention_record(
    vault: Path, kind_plural: str, identity: str, pointer: dict[str, Any]
) -> None:
    path = (
        vault
        / "retention"
        / kind_plural
        / identity
        / f"{pointer['snapshot_key']}.json"
    )
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "kind": pointer["kind"],
            "identity": identity,
            "snapshot_key": pointer["snapshot_key"],
            "snapshot_path": pointer["snapshot_path"],
            "bundle_sha256": pointer["bundle_sha256"],
            "retention": pointer["retention"],
        },
    )


def rebuild_retention_manifest(vault: Path) -> dict[str, Any]:
    records = []
    for path in sorted((vault / "retention").glob("*/*/*.json")):
        try:
            records.append(_read_json(path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    deadlines = [
        item.get("retention", {}).get("delete_or_refresh_by")
        for item in records
        if item.get("retention", {}).get("delete_or_refresh_by")
    ]
    manifest = {
        "schema_version": "1.0",
        "updated_at": _iso(datetime.now(timezone.utc)),
        "record_count": len(records),
        "api_record_count": sum(
            1
            for item in records
            if item.get("retention", {}).get("data_origin")
            == "youtube-data-api-v3"
        ),
        "next_delete_or_refresh_by": min(deadlines) if deadlines else None,
        "policy": {
            "non_authorized_api_data": "REFRESH_OR_DELETE_WITHIN_30_DAYS",
            "transcripts_and_internal_provenance": "SEPARATELY_CLASSIFIED",
        },
    }
    _write_json(vault / "retention" / "manifest.json", manifest)
    return manifest


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "snapshot-metadata.json":
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative_to_vault(path: Path, container: Path) -> str:
    vault = container.parents[1]
    return path.relative_to(vault).as_posix() + "/"


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("snapshot timestamp is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish immutable private AITube snapshots and atomic memory indexes."
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--authorization-mode", default="api_key_non_authorized")
    parser.add_argument("--refresh-days", type=int, default=DEFAULT_REFRESH_DAYS)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = publish_snapshot_batch(
        args.source_root,
        args.vault,
        args.batch_id,
        authorization_mode=args.authorization_mode,
        retention_days=args.retention_days,
        refresh_days=args.refresh_days,
    )
    print(f"SNAPSHOT_BATCH={result['batch']['snapshot_key']}")
    print(f"SNAPSHOT_VIDEOS={len(result['videos'])}")
    print(f"SNAPSHOT_CHANNELS={len(result['channels'])}")
    print("ATOMIC_MEMORY_INDEX=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
