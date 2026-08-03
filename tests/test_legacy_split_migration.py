from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from aitubetranscript.legacy_split_migration import migrate_legacy_results


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_legacy_latest_migrates_without_refetch(tmp_path: Path) -> None:
    video_id = "abcdefghijk"
    source = tmp_path / "source"
    video = source / video_id
    _write_json(
        video / "receipt.json",
        {
            "video_id": video_id,
            "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
            "fetched_at": "2026-08-03T00:00:00Z",
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "transcript_source": "youtube-transcript.ai:en",
            "segment_count": 1,
            "comments_status": "PROVEN",
            "comments_coverage_status": "PROVEN",
            "comment_count": 5,
        },
    )
    _write_json(
        video / "transcript-manifest.json",
        {"chunks": ["chunks/001.md"], "coverage": {"status": "PROVEN"}},
    )
    _write_json(
        video / "reader-manifest.json",
        {"transcript": {"chunks": ["chunks/001.md"]}},
    )
    (video / "chunks").mkdir(parents=True)
    (video / "chunks" / "001.md").write_text("transcript", encoding="utf-8")
    (video / "description.md").write_text("description", encoding="utf-8")
    (video / "comments.md").write_text("comments", encoding="utf-8")
    _write_json(video / "comments-manifest.json", {"coverage": {"status": "PROVEN"}})
    _write_json(
        video / "result.json",
        {
            "metadata": {
                "title": "Legacy example",
                "channel": "Legacy channel",
                "upload_date": "20260801",
            },
            "transcript": {"segments": [{"start": 0, "duration": 1}]},
            "comments": {},
        },
    )

    batch = source / "batches" / "legacy-batch"
    _write_json(
        batch / "batch-receipt.json",
        {
            "batch_id": "legacy-batch",
            "status": "PROVEN",
            "started_at": "2026-08-03T00:00:00Z",
            "completed_at": "2026-08-03T00:00:01Z",
            "request_sha256": "legacy-request",
            "results": [{"video_id": video_id, "status": "PROVEN"}],
            "coverage": {"status": "PROVEN", "exactly_once": True},
        },
    )
    _write_json(batch / "batch-reader-manifest.json", {"batch_id": "legacy-batch"})

    legacy = tmp_path / "legacy"
    shutil.copytree(video, legacy / "videos" / video_id / "latest")
    shutil.copytree(batch, legacy / "batches" / "legacy-batch" / "latest")
    _write_json(
        legacy / "memory" / "by-video-id" / f"{video_id}.json",
        {
            "request_profile": {
                "languages": "en",
                "comments_requested": 5,
            }
        },
    )

    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    result = migrate_legacy_results(
        legacy,
        durable,
        volatile,
        now=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert result["durable_videos"] == 1
    assert result["volatile_videos"] == 1
    assert result["durable_batches"] == 1
    durable_pointer = json.loads(
        (durable / "memory" / "by-video-id" / f"{video_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert durable_pointer["request_profile"]["legacy_inferred"] is True
    assert (volatile / "memory" / "by-video-id" / f"{video_id}.json").is_file()
