from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .storage_common import (
    VOLATILE_BRANCH,
    copy_file,
    copy_immutable_tree,
    iso,
    json_sha256,
    parse_datetime,
    read_json,
    replace_tree,
    safe_component,
    snapshot_key,
    tree_sha256,
    trust_record,
    write_json,
    write_jsonl,
)


def publish_durable_video(
    *,
    source: Path,
    root: Path,
    video_id: str,
    fetched_at: Any,
    profile: dict[str, Any],
) -> dict[str, Any]:
    receipt = read_json(source / "receipt.json")
    transcript_manifest = read_json(source / "transcript-manifest.json")
    chunks = _manifest_chunks(source, transcript_manifest)
    fetched = parse_datetime(fetched_at)

    with tempfile.TemporaryDirectory(prefix="aitube-durable-") as work:
        staging = Path(work)
        write_json(
            staging / "receipt.json",
            {
                "schema_version": "3.0",
                "storage_class": "DURABLE_TRANSCRIPT_EVIDENCE",
                "video_id": video_id,
                "canonical_url": receipt.get("canonical_url")
                or f"https://www.youtube.com/watch?v={video_id}",
                "fetched_at": iso(fetched),
                "transcript_status": receipt.get("transcript_status"),
                "transcript_coverage_status": receipt.get(
                    "transcript_coverage_status"
                ),
                "transcript_source": receipt.get("transcript_source"),
                "segment_count": int(receipt.get("segment_count") or 0),
            },
        )
        copy_file(
            source / "transcript-manifest.json",
            staging / "transcript-manifest.json",
        )
        copy_file(
            source / "transcript.md",
            staging / "transcript.md",
            required=False,
        )
        for relative in chunks:
            copy_file(source / relative, staging / relative)
        write_json(
            staging / "reader-manifest.json",
            {
                "schema_version": "3.0",
                "video_id": video_id,
                "reading_scope": "TRANSCRIPT_ONLY",
                "transcript": {
                    "status": receipt.get("transcript_status"),
                    "segment_count": int(receipt.get("segment_count") or 0),
                    "manifest": "transcript-manifest.json",
                    "chunks": chunks,
                },
                "read_order": ["transcript-manifest.json", *chunks],
            },
        )
        bundle_sha = tree_sha256(staging)
        profile_sha = json_sha256(profile)
        key = snapshot_key(fetched, profile_sha, bundle_sha)
        container = root / "videos" / video_id
        snapshot = container / "snapshots" / key
        metadata = {
            "schema_version": "3.0",
            "storage_class": "DURABLE_TRANSCRIPT_EVIDENCE",
            "kind": "video",
            "identity": video_id,
            "snapshot_key": key,
            "snapshot_path": f"videos/{video_id}/snapshots/{key}/",
            "fetched_at": iso(fetched),
            "request_profile": profile,
            "request_profile_sha256": profile_sha,
            "bundle_sha256": bundle_sha,
            "evidence": {
                "transcript_status": receipt.get("transcript_status"),
                "transcript_coverage_status": receipt.get(
                    "transcript_coverage_status"
                ),
                "segment_count": int(receipt.get("segment_count") or 0),
            },
            "api_overlay": {
                "branch": VOLATILE_BRANCH,
                "path": f"videos/{video_id}/overlays/{key}/",
            },
            "trust": trust_record(),
        }
        write_json(staging / "snapshot-metadata.json", metadata)
        copy_immutable_tree(
            staging,
            snapshot,
            digest=bundle_sha,
            metadata_name="snapshot-metadata.json",
            digest_field="bundle_sha256",
        )
        replace_tree(snapshot, container / "latest")
        pointer = durable_pointer(metadata)
        write_json(container / "pointers" / "latest.json", pointer)
        write_best_transcript_pointer(container)
        write_json(root / "memory" / "by-video-id" / f"{video_id}.json", pointer)
        return pointer


def publish_durable_batch(
    *,
    root: Path,
    batch_id: str,
    receipt: dict[str, Any],
    durable_videos: list[dict[str, Any]],
) -> dict[str, Any]:
    fetched = parse_datetime(receipt.get("completed_at") or receipt.get("started_at"))
    profile = {"request_sha256": receipt.get("request_sha256")}
    with tempfile.TemporaryDirectory(prefix="aitube-batch-") as work:
        staging = Path(work)
        write_json(
            staging / "batch-receipt.json",
            {
                "schema_version": "3.0",
                "storage_class": "DURABLE_INTERNAL_PROVENANCE",
                "batch_id": batch_id,
                "status": receipt.get("status"),
                "started_at": receipt.get("started_at"),
                "completed_at": receipt.get("completed_at"),
                "request_sha256": receipt.get("request_sha256"),
                "resolved_video_count": len(durable_videos),
                "video_ids": [item["identity"] for item in durable_videos],
                "coverage": receipt.get("coverage") or {},
            },
        )
        write_json(
            staging / "batch-reader-manifest.json",
            {
                "schema_version": "3.0",
                "batch_id": batch_id,
                "reading_scope": "TRANSCRIPT_ONLY",
                "video_readers": [
                    {
                        "video_id": item["identity"],
                        "snapshot_path": item["snapshot_path"],
                        "reader_manifest_path": item["reader_manifest_path"],
                    }
                    for item in durable_videos
                ],
            },
        )
        digest = tree_sha256(staging)
        profile_sha = json_sha256(profile)
        key = snapshot_key(fetched, profile_sha, digest)
        container = root / "batches" / batch_id
        snapshot = container / "snapshots" / key
        metadata = {
            "schema_version": "3.0",
            "storage_class": "DURABLE_INTERNAL_PROVENANCE",
            "kind": "batch",
            "identity": batch_id,
            "snapshot_key": key,
            "snapshot_path": f"batches/{batch_id}/snapshots/{key}/",
            "fetched_at": iso(fetched),
            "request_profile": profile,
            "request_profile_sha256": profile_sha,
            "bundle_sha256": digest,
            "trust": trust_record(),
        }
        write_json(staging / "snapshot-metadata.json", metadata)
        copy_immutable_tree(
            staging,
            snapshot,
            digest=digest,
            metadata_name="snapshot-metadata.json",
            digest_field="bundle_sha256",
        )
        replace_tree(snapshot, container / "latest")
        pointer = durable_pointer(metadata)
        write_json(container / "pointers" / "latest.json", pointer)
        write_json(container / "pointers" / "best.json", pointer)
        write_json(
            root / "memory" / "by-batch-id" / f"{safe_component(batch_id, 100)}.json",
            pointer,
        )
        return pointer


def write_best_transcript_pointer(container: Path) -> None:
    candidates = [
        read_json(path)
        for path in (container / "snapshots").glob("*/snapshot-metadata.json")
    ]
    if not candidates:
        return
    proven = [
        item
        for item in candidates
        if (item.get("evidence") or {}).get("transcript_status") == "PROVEN"
        and (item.get("evidence") or {}).get("transcript_coverage_status") == "PROVEN"
    ]
    chosen = max(
        proven or candidates,
        key=lambda item: (
            str(item.get("request_profile", {}).get("languages") or ""),
            str(item.get("fetched_at") or ""),
            str(item.get("bundle_sha256") or ""),
        ),
    )
    pointer = durable_pointer(chosen)
    write_json(container / "pointers" / "best-transcript.json", pointer)
    write_json(container / "pointers" / "best.json", pointer)


def rebuild_durable_indexes(root: Path) -> dict[str, int]:
    videos = [
        read_json(path)
        for path in sorted((root / "memory" / "by-video-id").glob("*.json"))
    ]
    batches = [
        read_json(path)
        for path in sorted((root / "memory" / "by-batch-id").glob("*.json"))
    ]
    write_jsonl(root / "memory" / "video-index.jsonl", videos)
    write_jsonl(root / "memory" / "batch-index.jsonl", batches)
    write_json(
        root / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "DURABLE_POINTER_INDEX",
            "video_count": len(videos),
            "batch_count": len(batches),
            "lookup_roots": {
                "video_id": "memory/by-video-id/",
                "batch_id": "memory/by-batch-id/",
            },
            "volatile_branch": VOLATILE_BRANCH,
            "volatile_memory_manifest": "memory/bank-manifest.json",
        },
    )
    return {"videos": len(videos), "batches": len(batches)}


def durable_pointer(metadata: dict[str, Any]) -> dict[str, Any]:
    base = str(metadata["snapshot_path"])
    kind = str(metadata["kind"])
    reader = (
        "reader-manifest.json"
        if kind == "video"
        else "batch-reader-manifest.json"
    )
    receipt = "receipt.json" if kind == "video" else "batch-receipt.json"
    return {
        "schema_version": "3.0",
        "storage_class": metadata["storage_class"],
        "kind": kind,
        "identity": metadata["identity"],
        "snapshot_key": metadata["snapshot_key"],
        "snapshot_path": base,
        "reader_manifest_path": base + reader,
        "receipt_path": base + receipt,
        "fetched_at": metadata["fetched_at"],
        "request_profile": metadata.get("request_profile") or {},
        "request_profile_sha256": metadata.get("request_profile_sha256"),
        "bundle_sha256": metadata.get("bundle_sha256"),
        "evidence": metadata.get("evidence") or {},
        "api_overlay": metadata.get("api_overlay") or {},
        "trust": metadata.get("trust") or {},
    }


def _manifest_chunks(source: Path, manifest: dict[str, Any]) -> list[str]:
    for key in ("chunks", "files"):
        value = manifest.get(key)
        if isinstance(value, list):
            return _normalize_chunk_entries(value)
    reader_path = source / "reader-manifest.json"
    if reader_path.is_file():
        reader = read_json(reader_path)
        section = reader.get("transcript") or {}
        chunks = section.get("chunks")
        if isinstance(chunks, list):
            return _normalize_chunk_entries(chunks)
    return sorted(
        path.relative_to(source).as_posix()
        for path in (source / "chunks").glob("*.md")
    )


def _normalize_chunk_entries(entries: list[Any]) -> list[str]:
    paths: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            raw = entry
        elif isinstance(entry, dict):
            raw = entry.get("path") or entry.get("file") or entry.get("filename")
            if not raw:
                raise ValueError("structured transcript chunk entry has no path")
        else:
            raise TypeError("transcript chunk entry must be a path string or object")
        candidate = Path(str(raw))
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"unsafe transcript chunk path: {raw}")
        paths.append(candidate.as_posix())
    return paths
