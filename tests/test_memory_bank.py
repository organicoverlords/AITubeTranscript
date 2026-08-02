import json

from aitubetranscript.memory_bank import update_memory_bank


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _video(vault, video_id="JsrwIGbuM8o"):
    root = vault / "videos" / video_id / "latest"
    _write_json(
        root / "result.json",
        {
            "metadata": {
                "title": '"Are We All Actually F\'d?"',
                "channel": "Gamers Nexus",
                "channel_id": "UChIs72whgZI9w6d6FhwGGHA",
                "upload_date": "20260618",
                "duration": 1714,
            },
            "transcript": {
                "segments": [
                    {"text": "Hello", "start": 0.0, "duration": 1.0}
                ]
            },
        },
    )
    _write_json(
        root / "receipt.json",
        {
            "video_id": video_id,
            "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
            "fetched_at": "2026-08-02T22:02:35+00:00",
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "transcript_source": "test",
            "segment_count": 1,
            "comments_status": "PROVEN",
            "comments_coverage_status": "PROVEN",
            "comment_count": 10,
        },
    )
    _write_json(root / "reader-manifest.json", {"read_order": ["description.md"]})
    return root


def test_video_memory_index_and_logical_download_name(tmp_path):
    root = _video(tmp_path)
    counts = update_memory_bank(tmp_path, video_ids=["JsrwIGbuM8o"])

    assert counts == {"videos": 1, "channels": 0, "batches": 0}
    entry = json.loads((root / "memory-entry.json").read_text())
    assert entry["memory_key"] == "youtube:JsrwIGbuM8o"
    assert entry["published_date"] == "2026-06-18"
    assert entry["duration_readable"] == "28:34"
    assert entry["friendly_name"].startswith(
        "2026-06-18__gamers-nexus__are-we-all-actually-f-d"
    )
    assert entry["friendly_name"].endswith("__JsrwIGbuM8o")
    assert (root / "download-name.txt").read_text().strip().endswith(
        "__JsrwIGbuM8o__aitube-memory"
    )
    assert (tmp_path / "memory/by-video-id/JsrwIGbuM8o.json").is_file()
    pointer = tmp_path / "memory/by-title" / f"{entry['friendly_name']}.json"
    assert pointer.is_file()
    assert "Gamers Nexus" in (tmp_path / "memory/video-index.md").read_text()


def test_rebuild_all_backfills_existing_video(tmp_path):
    _video(tmp_path, "x8W_S9zmodk")
    counts = update_memory_bank(tmp_path, rebuild_all=True)

    assert counts["videos"] == 1
    assert (tmp_path / "memory/by-video-id/x8W_S9zmodk.json").is_file()


def test_batch_and_channel_indexes(tmp_path):
    _video(tmp_path)
    channel_root = tmp_path / "channels/UChIs72whgZI9w6d6FhwGGHA/latest"
    _write_json(
        channel_root / "channel-receipt.json",
        {
            "channel_id": "UChIs72whgZI9w6d6FhwGGHA",
            "channel_title": "Gamers Nexus",
            "fetched_at": "2026-08-02T22:03:42+00:00",
            "status": "PARTIAL",
            "video_count": 5,
            "catalog_exhausted": False,
            "next_start_index": 5,
        },
    )
    _write_json(
        channel_root / "channel-catalog.json",
        {
            "channel": {"reported_video_count": 3300},
            "videos": [
                {"published_date": "2026-08-01"},
                {"published_date": "2026-07-22"},
            ],
        },
    )
    batch_root = tmp_path / "batches/batch-001/latest"
    receipt = {
        "batch_id": "batch-001",
        "status": "PARTIAL",
        "started_at": "2026-08-02T22:03:42+00:00",
        "completed_at": "2026-08-02T22:03:43+00:00",
        "duration_seconds": 1.0,
        "resolved_video_count": 1,
        "proven_count": 1,
        "partial_count": 0,
        "failed_count": 0,
        "request": {"video_urls": ["url"], "playlist_urls": [], "channel_urls": []},
        "results": [{"video_id": "JsrwIGbuM8o", "status": "PROVEN"}],
        "channel_catalogs": [{"channel_id": "UChIs72whgZI9w6d6FhwGGHA"}],
    }
    _write_json(batch_root / "batch-receipt.json", receipt)

    counts = update_memory_bank(
        tmp_path,
        batch_receipt=batch_root / "batch-receipt.json",
    )
    assert counts == {"videos": 1, "channels": 1, "batches": 1}
    assert (tmp_path / "memory/channel-index.jsonl").is_file()
    assert (tmp_path / "memory/batch-index.jsonl").is_file()
    manifest = json.loads((tmp_path / "memory/bank-manifest.json").read_text())
    assert manifest["video_count"] == 1
    assert manifest["channel_count"] == 1
    assert manifest["batch_count"] == 1
