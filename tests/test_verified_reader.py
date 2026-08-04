from __future__ import annotations

from datetime import datetime, timezone

from aitubetranscript.storage_common import write_json
from aitubetranscript.verified_reader import build_verified_reading

VIDEO_ID = "ABCDEFGHIJK"
SNAPSHOT_KEY = "20260805T000000000000Z__profile__bundle"


def _fixture(tmp_path, *, missing_chunk: bool = False):
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    snapshot = durable / "videos" / VIDEO_ID / "snapshots" / SNAPSHOT_KEY
    overlay = volatile / "videos" / VIDEO_ID / "overlays" / SNAPSHOT_KEY
    write_json(
        durable / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "DURABLE_POINTER_INDEX",
            "volatile_branch": "aitube-volatile",
        },
    )
    write_json(
        volatile / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "VOLATILE_API_MEMORY_INDEX",
            "durable_branch": "aitube-durable",
        },
    )
    write_json(
        snapshot / "snapshot-metadata.json",
        {
            "schema_version": "3.0",
            "snapshot_key": SNAPSHOT_KEY,
            "snapshot_path": f"videos/{VIDEO_ID}/snapshots/{SNAPSHOT_KEY}/",
            "fetched_at": "2026-08-05T00:00:00Z",
            "request_profile": {"languages": "en", "transcript_source": "captions:en"},
            "bundle_sha256": "bundle",
            "evidence": {
                "transcript_status": "PROVEN",
                "transcript_coverage_status": "PROVEN",
            },
            "api_overlay": {
                "path": f"videos/{VIDEO_ID}/overlays/{SNAPSHOT_KEY}/"
            },
        },
    )
    write_json(
        snapshot / "reader-manifest.json",
        {
            "schema_version": "3.0",
            "video_id": VIDEO_ID,
            "read_order": ["transcript-manifest.json", "chunks/001.md"],
        },
    )
    write_json(snapshot / "transcript-manifest.json", {"coverage": {"status": "PROVEN"}})
    if not missing_chunk:
        (snapshot / "chunks").mkdir(parents=True, exist_ok=True)
        (snapshot / "chunks" / "001.md").write_text("complete transcript", encoding="utf-8")
    write_json(
        overlay / "overlay-metadata.json",
        {
            "overlay_path": f"videos/{VIDEO_ID}/overlays/{SNAPSHOT_KEY}/",
            "fetched_at": "2026-08-05T00:00:00Z",
            "comment_count": 1,
            "comments_status": "PROVEN",
            "comments_coverage_status": "PROVEN",
            "retention": {
                "refresh_due_at": "2026-08-20T00:00:00Z",
                "delete_or_refresh_by": "2026-09-04T00:00:00Z",
            },
        },
    )
    (overlay / "description.md").write_text("description", encoding="utf-8")
    write_json(overlay / "comments-manifest.json", {"chunks": ["comment-chunks/001.md"]})
    (overlay / "comment-chunks").mkdir(parents=True, exist_ok=True)
    (overlay / "comment-chunks" / "001.md").write_text("comment", encoding="utf-8")
    return durable, volatile


def test_verified_reader_materializes_transcript_pack_and_access_receipt(tmp_path):
    durable, volatile = _fixture(tmp_path)
    output = tmp_path / "output"
    result = build_verified_reading(
        [VIDEO_ID],
        durable_root=durable,
        volatile_root=volatile,
        output_dir=output,
        mode="TRANSCRIPT_COMPLETE",
        purpose="unit test",
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert result["reading_coverage"] == "PROVEN"
    assert result["completed_video_count"] == 1
    assert "complete transcript" in (output / "reading-pack.md").read_text(encoding="utf-8")
    assert (output / "access-receipt.json").is_file()
    assert (output / "access-ledger.jsonl").is_file()


def test_verified_reader_full_mode_reads_volatile_bundle(tmp_path):
    durable, volatile = _fixture(tmp_path)
    output = tmp_path / "output"
    result = build_verified_reading(
        [VIDEO_ID],
        durable_root=durable,
        volatile_root=volatile,
        output_dir=output,
        mode="FULL_RESEARCH_COMPLETE",
        min_comments=1,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert result["reading_coverage"] == "PROVEN"
    pack = (output / "reading-pack.md").read_text(encoding="utf-8")
    assert "description" in pack
    assert "comment" in pack


def test_verified_reader_fails_closed_on_missing_manifest_chunk(tmp_path):
    durable, volatile = _fixture(tmp_path, missing_chunk=True)
    result = build_verified_reading(
        [VIDEO_ID],
        durable_root=durable,
        volatile_root=volatile,
        output_dir=tmp_path / "output",
        mode="TRANSCRIPT_COMPLETE",
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert result["reading_coverage"] == "BLOCKED"
    assert result["missing_video_ids"] == [VIDEO_ID]
    assert result["videos"][0]["missing_durable_files"]


def test_verified_reader_resolves_durable_batch(tmp_path):
    durable, volatile = _fixture(tmp_path)
    batch_id = "research-batch"
    batch_key = "batch-snapshot"
    batch_snapshot = durable / "batches" / batch_id / "snapshots" / batch_key
    write_json(
        durable / "memory" / "by-batch-id" / f"{batch_id}.json",
        {
            "snapshot_path": f"batches/{batch_id}/snapshots/{batch_key}/",
        },
    )
    write_json(
        batch_snapshot / "batch-reader-manifest.json",
        {"video_readers": [{"video_id": VIDEO_ID}]},
    )
    write_json(
        batch_snapshot / "batch-receipt.json",
        {
            "resolved_video_count": 1,
            "coverage": {
                "exactly_once": True,
                "missing_indices": [],
                "duplicate_indices": [],
                "unexpected_indices": [],
            },
        },
    )
    result = build_verified_reading(
        batch_id=batch_id,
        durable_root=durable,
        volatile_root=volatile,
        output_dir=tmp_path / "output",
        mode="TRANSCRIPT_COMPLETE",
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert result["reading_coverage"] == "PROVEN"
    assert result["batch"]["status"] == "PROVEN"
    assert result["selected_video_count"] == 1
