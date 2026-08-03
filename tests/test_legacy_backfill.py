from __future__ import annotations

import json
from pathlib import Path

from aitubetranscript.legacy_backfill import backfill_legacy_latest


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _make_legacy_video(vault: Path, video_id: str) -> None:
    latest = vault / "videos" / video_id / "latest"
    _write_json(
        latest / "receipt.json",
        {
            "video_id": video_id,
            "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
            "fetched_at": "2026-08-01T00:00:00Z",
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "comments_status": "PROVEN",
            "comments_coverage_status": "PROVEN",
            "segment_count": 2,
            "comment_count": 100,
            "transcript_source": "youtube-transcript.ai:en",
        },
    )
    _write_json(
        latest / "result.json",
        {
            "metadata": {
                "title": "Legacy example",
                "channel": "Example channel",
                "channel_id": "UCexample",
                "upload_date": "20260731",
            },
            "transcript": {
                "segments": [
                    {"start": 0, "duration": 5, "text": "one"},
                    {"start": 5, "duration": 5, "text": "two"},
                ]
            },
        },
    )
    _write_json(
        latest / "reader-manifest.json",
        {
            "read_order": ["description.md", "transcript.md", "comments.md"],
            "transcript": {"status": "PROVEN"},
        },
    )
    _write_json(
        latest / "transcript-manifest.json",
        {"coverage": {"status": "PROVEN"}},
    )
    _write_json(
        latest / "comments-manifest.json",
        {"coverage": {"status": "PROVEN"}},
    )
    (latest / "description.md").write_text("description", encoding="utf-8")
    (latest / "transcript.md").write_text("transcript", encoding="utf-8")
    (latest / "comments.md").write_text("comments", encoding="utf-8")


def _make_legacy_batch(vault: Path, batch_id: str, video_id: str) -> None:
    latest = vault / "batches" / batch_id / "latest"
    _write_json(
        latest / "batch-receipt.json",
        {
            "batch_id": batch_id,
            "started_at": "2026-08-01T00:00:00Z",
            "completed_at": "2026-08-01T00:00:01Z",
            "request_sha256": "legacy-request",
            "request": {"comments": 100, "languages": "en"},
            "resolved_video_count": 1,
            "channel_catalogs": [],
            "results": [{"video_id": video_id, "status": "PROVEN"}],
        },
    )
    _write_json(latest / "batch-reader-manifest.json", {"batch_id": batch_id})


def test_backfills_legacy_latest_once_and_promotes_memory(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    video_id = "abcdefghijk"
    _make_legacy_video(vault, video_id)
    _make_legacy_batch(vault, "legacy-batch", video_id)

    first = backfill_legacy_latest(vault)

    assert first["videos"] == 1
    assert first["batches"] == 1
    assert (vault / "videos" / video_id / "pointers" / "best.json").is_file()
    assert (vault / "batches" / "legacy-batch" / "pointers" / "latest.json").is_file()
    assert (vault / "retention" / "manifest.json").is_file()

    memory = json.loads(
        (vault / "memory" / "by-video-id" / f"{video_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert memory["comment_count"] == 100
    assert "/snapshots/" in memory["preferred_result_path"]
    assert memory["request_profile"]["legacy_inferred"] is True

    second = backfill_legacy_latest(vault)
    assert second["videos"] == 0
    assert second["batches"] == 0
    assert second["skipped"] >= 2
    assert len(list((vault / "videos" / video_id / "snapshots").iterdir())) == 1
