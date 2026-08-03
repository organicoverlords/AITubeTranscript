from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aitubetranscript.retention_maintenance import maintain_volatile_store
from aitubetranscript.snapshot_selector import select_video_snapshot
from aitubetranscript.split_store import publish_split_batch


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _make_video(
    root: Path,
    *,
    video_id: str,
    fetched_at: str,
    comments_requested: int,
    comments_retrieved: int,
    transcript_text: str,
) -> None:
    video = root / video_id
    _write_json(
        video / "receipt.json",
        {
            "video_id": video_id,
            "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
            "fetched_at": fetched_at,
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "transcript_source": "youtube-transcript.ai:en",
            "segment_count": 2,
            "comments_status": "PROVEN" if comments_requested else "NOT_REQUESTED",
            "comments_coverage_status": (
                "PROVEN" if comments_requested else "NOT_REQUESTED"
            ),
            "comment_count": comments_retrieved,
        },
    )
    _write_json(
        video / "transcript-manifest.json",
        {
            "chunks": ["chunks/001.md"],
            "coverage": {"status": "PROVEN"},
        },
    )
    _write_json(
        video / "reader-manifest.json",
        {"transcript": {"chunks": ["chunks/001.md"]}},
    )
    (video / "chunks").mkdir(parents=True, exist_ok=True)
    (video / "chunks" / "001.md").write_text(transcript_text, encoding="utf-8")
    (video / "transcript.md").write_text(transcript_text, encoding="utf-8")
    (video / "description.md").write_text("API description", encoding="utf-8")
    (video / "comments.md").write_text("API comments", encoding="utf-8")
    _write_json(
        video / "comments-manifest.json",
        {"coverage": {"status": "PROVEN"}},
    )
    (video / "comment-chunks").mkdir()
    (video / "comment-chunks" / "001.md").write_text(
        "API comment", encoding="utf-8"
    )
    _write_json(
        video / "result.json",
        {
            "metadata": {
                "title": "Example video",
                "channel": "Example channel",
                "channel_id": "UCexample",
                "upload_date": "20260801",
                "duration": 123,
            },
            "transcript": {
                "segments": [{"start": 0, "duration": 2, "text": transcript_text}]
            },
            "comments": {"items": [{"text": "API comment"}]},
        },
    )


def _make_batch(
    root: Path,
    *,
    batch_id: str,
    video_id: str,
    completed_at: str,
    comments: int,
) -> None:
    batch = root / "batches" / batch_id
    _write_json(
        batch / "batch-receipt.json",
        {
            "batch_id": batch_id,
            "status": "PROVEN",
            "started_at": completed_at,
            "completed_at": completed_at,
            "request_sha256": f"request-{batch_id}",
            "request": {
                "languages": "en",
                "comments": comments,
                "whisper": False,
            },
            "results": [{"video_id": video_id, "status": "PROVEN"}],
            "channel_catalogs": [],
            "coverage": {
                "status": "PROVEN",
                "exactly_once": True,
                "missing_indices": [],
                "duplicate_indices": [],
                "unexpected_indices": [],
                "ordered_contiguous": True,
            },
        },
    )
    _write_json(batch / "batch-reader-manifest.json", {"batch_id": batch_id})


def test_split_keeps_api_payload_out_of_durable_history(tmp_path: Path) -> None:
    video_id = "abcdefghijk"
    source = tmp_path / "source"
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    _make_video(
        source,
        video_id=video_id,
        fetched_at="2026-08-03T00:00:00.123456Z",
        comments_requested=100,
        comments_retrieved=100,
        transcript_text="durable transcript",
    )
    _make_batch(
        source,
        batch_id="batch",
        video_id=video_id,
        completed_at="2026-08-03T00:00:01Z",
        comments=100,
    )

    result = publish_split_batch(source, durable, volatile, "batch")
    key = result["durable_videos"][0]["snapshot_key"]
    durable_snapshot = durable / "videos" / video_id / "snapshots" / key
    overlay = volatile / "videos" / video_id / "overlays" / key

    assert (durable_snapshot / "chunks" / "001.md").is_file()
    assert (durable_snapshot / "transcript-manifest.json").is_file()
    assert not (durable_snapshot / "description.md").exists()
    assert not (durable_snapshot / "comments.md").exists()
    assert not (durable_snapshot / "comments-manifest.json").exists()
    assert not (durable_snapshot / "result.json").exists()
    assert (overlay / "description.md").is_file()
    assert (overlay / "comments.md").is_file()
    assert (overlay / "api-result.json").is_file()


def test_requirement_selector_rejects_newer_smaller_comment_overlay(
    tmp_path: Path,
) -> None:
    video_id = "abcdefghijk"
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"

    first = tmp_path / "first"
    _make_video(
        first,
        video_id=video_id,
        fetched_at="2026-08-01T00:00:00.100000Z",
        comments_requested=100,
        comments_retrieved=100,
        transcript_text="first transcript",
    )
    _make_batch(
        first,
        batch_id="batch-100",
        video_id=video_id,
        completed_at="2026-08-01T00:00:01Z",
        comments=100,
    )
    publish_split_batch(first, durable, volatile, "batch-100")

    second = tmp_path / "second"
    _make_video(
        second,
        video_id=video_id,
        fetched_at="2026-08-02T00:00:00.100000Z",
        comments_requested=10,
        comments_retrieved=10,
        transcript_text="second transcript",
    )
    _make_batch(
        second,
        batch_id="batch-10",
        video_id=video_id,
        completed_at="2026-08-02T00:00:01Z",
        comments=10,
    )
    publish_split_batch(second, durable, volatile, "batch-10")

    selected = select_video_snapshot(
        durable,
        video_id,
        volatile_root=volatile,
        language="en",
        min_comments=100,
        now=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert selected["selection_status"] == "SATISFIED"
    assert selected["api_overlay_path"]
    assert "20260801" in selected["selected_snapshot_key"]
    assert selected["reasons"][-1] == "100 comments satisfy minimum"


def test_snapshot_key_uses_microseconds_and_bundle_hash(tmp_path: Path) -> None:
    video_id = "abcdefghijk"
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"

    for batch_id, text in (("one", "one"), ("two", "two")):
        source = tmp_path / batch_id
        _make_video(
            source,
            video_id=video_id,
            fetched_at="2026-08-03T00:00:00.123456Z",
            comments_requested=0,
            comments_retrieved=0,
            transcript_text=text,
        )
        _make_batch(
            source,
            batch_id=batch_id,
            video_id=video_id,
            completed_at="2026-08-03T00:00:01Z",
            comments=0,
        )
        publish_split_batch(source, durable, volatile, batch_id)

    keys = [
        path.name
        for path in (durable / "videos" / video_id / "snapshots").iterdir()
    ]
    assert len(keys) == 2
    assert keys[0] != keys[1]
    assert all("123456Z" in key for key in keys)


def test_expired_overlay_is_purged_and_memory_pointer_removed(
    tmp_path: Path,
) -> None:
    video_id = "abcdefghijk"
    source = tmp_path / "source"
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    _make_video(
        source,
        video_id=video_id,
        fetched_at="2026-01-01T00:00:00Z",
        comments_requested=10,
        comments_retrieved=10,
        transcript_text="still durable",
    )
    _make_batch(
        source,
        batch_id="batch",
        video_id=video_id,
        completed_at="2026-01-01T00:00:01Z",
        comments=10,
    )
    publish_split_batch(
        source,
        durable,
        volatile,
        "batch",
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    result = maintain_volatile_store(
        volatile, now=datetime(2026, 2, 2, tzinfo=timezone.utc)
    )

    assert result["purge"]["removed_count"] >= 1
    assert not (volatile / "memory" / "by-video-id" / f"{video_id}.json").exists()
    assert (durable / "memory" / "by-video-id" / f"{video_id}.json").is_file()
