from __future__ import annotations

import json
from pathlib import Path

from aitubetranscript.snapshot_store import publish_snapshot_batch


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _make_video(
    root: Path,
    *,
    video_id: str,
    fetched_at: str,
    requested_comments: int,
    retrieved_comments: int,
) -> None:
    video = root / video_id
    video.mkdir(parents=True, exist_ok=True)
    _write_json(
        video / "receipt.json",
        {
            "video_id": video_id,
            "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
            "fetched_at": fetched_at,
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "comments_status": "PROVEN" if requested_comments else "NOT_REQUESTED",
            "comments_coverage_status": (
                "PROVEN" if requested_comments else "NOT_REQUESTED"
            ),
            "segment_count": 59,
            "comment_count": retrieved_comments,
            "transcript_source": "youtube-transcript.ai:en",
        },
    )
    _write_json(video / "reader-manifest.json", {"read_order": []})
    _write_json(video / "transcript-manifest.json", {"coverage": {"status": "PROVEN"}})
    _write_json(video / "comments-manifest.json", {"coverage": {"status": "PROVEN"}})
    _write_json(
        video / "result.json",
        {
            "metadata": {
                "title": "Example video",
                "channel": "Example channel",
                "channel_id": "UCexample",
                "upload_date": "20260618",
            },
            "transcript": {
                "segments": [{"start": 0, "duration": 30, "text": "example"}]
            },
        },
    )
    (video / "description.md").write_text("description", encoding="utf-8")
    (video / "transcript.md").write_text("transcript", encoding="utf-8")
    (video / "comments.md").write_text("comments", encoding="utf-8")


def _make_batch(
    root: Path,
    *,
    batch_id: str,
    video_id: str,
    completed_at: str,
    comments: int,
) -> None:
    batch = root / "batches" / batch_id
    batch.mkdir(parents=True, exist_ok=True)
    _write_json(
        batch / "batch-receipt.json",
        {
            "batch_id": batch_id,
            "started_at": completed_at,
            "completed_at": completed_at,
            "request_sha256": f"request-{batch_id}",
            "request": {
                "languages": "en",
                "comments": comments,
                "whisper": False,
            },
            "channel_catalogs": [],
            "results": [{"video_id": video_id, "status": "PROVEN"}],
        },
    )
    _write_json(batch / "batch-reader-manifest.json", {"batch_id": batch_id})


def test_newer_small_fetch_does_not_replace_best_complete_snapshot(tmp_path: Path) -> None:
    video_id = "abcdefghijk"
    vault = tmp_path / "vault"

    first = tmp_path / "first"
    _make_video(
        first,
        video_id=video_id,
        fetched_at="2026-08-01T00:00:00Z",
        requested_comments=100,
        retrieved_comments=100,
    )
    _make_batch(
        first,
        batch_id="batch-100",
        video_id=video_id,
        completed_at="2026-08-01T00:00:01Z",
        comments=100,
    )
    publish_snapshot_batch(first, vault, "batch-100")

    second = tmp_path / "second"
    _make_video(
        second,
        video_id=video_id,
        fetched_at="2026-08-02T00:00:00Z",
        requested_comments=10,
        retrieved_comments=10,
    )
    _make_batch(
        second,
        batch_id="batch-10",
        video_id=video_id,
        completed_at="2026-08-02T00:00:01Z",
        comments=10,
    )
    publish_snapshot_batch(second, vault, "batch-10")

    latest = json.loads(
        (vault / "videos" / video_id / "pointers" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    best = json.loads(
        (
            vault / "videos" / video_id / "pointers" / "best-complete.json"
        ).read_text(encoding="utf-8")
    )

    assert latest["evidence"]["comment_count"] == 10
    assert best["evidence"]["comment_count"] == 100
    assert len(list((vault / "videos" / video_id / "snapshots").iterdir())) == 2
    assert (vault / "retention" / "manifest.json").is_file()


def test_snapshot_metadata_marks_external_content_untrusted(tmp_path: Path) -> None:
    video_id = "abcdefghijk"
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    _make_video(
        source,
        video_id=video_id,
        fetched_at="2026-08-01T00:00:00Z",
        requested_comments=0,
        retrieved_comments=0,
    )
    _make_batch(
        source,
        batch_id="batch",
        video_id=video_id,
        completed_at="2026-08-01T00:00:01Z",
        comments=0,
    )

    publish_snapshot_batch(source, vault, "batch")
    pointer = json.loads(
        (vault / "videos" / video_id / "pointers" / "best.json").read_text(
            encoding="utf-8"
        )
    )

    assert pointer["trust"]["class"] == "EXTERNAL_UNTRUSTED_CONTENT"
    assert pointer["trust"]["may_control_tools"] is False
    assert pointer["retention"]["action"] == "REFRESH_OR_DELETE"
