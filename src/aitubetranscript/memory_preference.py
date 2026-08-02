from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import memory_bank as bank


def promote_preferred_video_entries(vault: Path, video_ids: list[str]) -> None:
    """Point compact memory indexes at the best immutable video snapshot."""
    vault = vault.resolve()
    videos = bank._load_index(vault / bank.VIDEO_INDEX, "video_id")

    for video_id in sorted(set(video_ids)):
        pointer_path = vault / "videos" / video_id / "pointers" / "best.json"
        if not pointer_path.is_file():
            continue
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        snapshot = vault / str(pointer["snapshot_path"])
        if not (snapshot / "receipt.json").is_file():
            continue

        with tempfile.TemporaryDirectory(prefix="aitube-memory-", dir=vault) as work:
            temporary = Path(work) / "latest"
            shutil.copytree(snapshot, temporary)
            entry = bank.ensure_video_memory_entry(temporary)

        entry.update(
            {
                "stable_result_path": pointer["snapshot_path"],
                "preferred_result_path": pointer["snapshot_path"],
                "latest_result_path": f"videos/{video_id}/latest/",
                "reader_manifest_path": pointer["reader_manifest_path"],
                "receipt_path": pointer["receipt_path"],
                "best_snapshot_key": pointer["snapshot_key"],
                "request_profile": pointer.get("request_profile") or {},
                "request_profile_sha256": pointer.get("request_profile_sha256"),
                "bundle_sha256": pointer.get("bundle_sha256"),
                "retention": pointer.get("retention") or {},
                "trust": pointer.get("trust") or {},
                "snapshot_pointer_paths": {
                    "latest": f"videos/{video_id}/pointers/latest.json",
                    "best": f"videos/{video_id}/pointers/best.json",
                    "best_transcript": (
                        f"videos/{video_id}/pointers/best-transcript.json"
                    ),
                    "best_comments": (
                        f"videos/{video_id}/pointers/best-comments.json"
                    ),
                    "best_complete": (
                        f"videos/{video_id}/pointers/best-complete.json"
                    ),
                },
            }
        )

        previous = videos.get(video_id)
        videos[video_id] = entry
        bank._write_video_pointers(vault, entry, previous)
        _write_latest_memory_helpers(vault, video_id, entry)

    ordered = sorted(
        videos.values(),
        key=lambda item: (
            str(item.get("published_date") or ""),
            str(item.get("fetched_at") or ""),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    bank._write_jsonl(vault / bank.VIDEO_INDEX, ordered)
    (vault / "memory" / "video-index.md").write_text(
        bank._video_index_markdown(ordered),
        encoding="utf-8",
    )

    manifest_path = vault / "memory" / "bank-manifest.json"
    if manifest_path.is_file():
        manifest = bank._read_json(manifest_path)
        manifest["video_count"] = len(ordered)
        manifest["updated_at"] = bank._utc_now()
        manifest["preferred_snapshot_policy"] = (
            "BEST_COMPLETE_THEN_BEST_TRANSCRIPT_THEN_LATEST"
        )
        bank._write_json(manifest_path, manifest)


def _write_latest_memory_helpers(
    vault: Path, video_id: str, entry: dict[str, Any]
) -> None:
    latest = vault / "videos" / video_id / "latest"
    if not latest.is_dir():
        return
    bank._write_json(latest / "memory-entry.json", entry)
    (latest / "memory-entry.md").write_text(
        bank._video_entry_markdown(entry),
        encoding="utf-8",
    )
    (latest / "download-name.txt").write_text(
        str(entry["suggested_download_folder"]) + "\n",
        encoding="utf-8",
    )
