from __future__ import annotations

import json

import pytest

from aitubetranscript import batch


def test_extract_playlist_id_from_playlist_and_watch_urls() -> None:
    playlist_id = "PL1234567890ABCDE"
    assert (
        batch.extract_playlist_id(
            f"https://www.youtube.com/playlist?list={playlist_id}"
        )
        == playlist_id
    )
    assert (
        batch.extract_playlist_id(
            f"https://www.youtube.com/watch?v=JsrwIGbuM8o&list={playlist_id}"
        )
        == playlist_id
    )


def test_normalize_batch_request_supports_videos_playlists_and_channels() -> None:
    request = batch.normalize_batch_request(
        {
            "request_id": "batch-test",
            "video_url": "https://www.youtube.com/watch?v=JsrwIGbuM8o",
            "video_urls": [
                "https://www.youtube.com/watch?v=JsrwIGbuM8o",
                "https://www.youtube.com/watch?v=x8W_S9zmodk",
            ],
            "playlist_url": "PL1234567890ABCDE",
            "channel_url": "https://www.youtube.com/@example",
            "research_channel_videos": True,
            "comments": 25,
            "max_videos": 50,
            "catalog_max_videos": 500,
            "concurrency": 3,
        }
    )

    assert request["video_urls"] == [
        "https://www.youtube.com/watch?v=JsrwIGbuM8o",
        "https://www.youtube.com/watch?v=x8W_S9zmodk",
    ]
    assert request["playlist_urls"] == ["PL1234567890ABCDE"]
    assert request["channel_urls"] == ["https://www.youtube.com/@example"]
    assert request["research_channel_videos"] is True
    assert request["comments"] == 25
    assert request["max_videos"] == 50
    assert request["catalog_max_videos"] == 500
    assert request["concurrency"] == 3


def test_fetch_playlist_video_ids_paginates_and_slices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = iter(
        [
            {
                "items": [
                    {"contentDetails": {"videoId": "AAAAAAAAAAA"}},
                    {"contentDetails": {"videoId": "BBBBBBBBBBB"}},
                ],
                "nextPageToken": "next",
            },
            {
                "items": [
                    {"contentDetails": {"videoId": "CCCCCCCCCCC"}},
                    {"contentDetails": {"videoId": "DDDDDDDDDDD"}},
                ]
            },
        ]
    )

    monkeypatch.setattr(batch, "_fetch_json", lambda *_args, **_kwargs: next(pages))
    video_ids, metadata = batch.fetch_playlist_video_ids(
        "PL1234567890ABCDE",
        "test-key",
        start_index=1,
        limit=2,
    )

    assert video_ids == ["BBBBBBBBBBB", "CCCCCCCCCCC"]
    assert metadata["api_pages"] == 2
    assert metadata["selected_count"] == 2
    assert metadata["catalog_exhausted"] is True
    assert metadata["truncated_by_limit"] is False
    assert metadata["next_start_index"] is None


def test_run_batch_writes_proven_accounting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    video_ids = ["JsrwIGbuM8o", "x8W_S9zmodk"]
    monkeypatch.setattr(
        batch,
        "_resolve_sources",
        lambda _request, _key, _output: (video_ids, [], [], 0),
    )

    def fake_fetch_one(video_id, *_args, **_kwargs):
        return {
            "index": 0,
            "video_id": video_id,
            "canonical_url": batch.canonical_url(video_id),
            "status": "PROVEN",
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "comments_status": "PROVEN",
            "comments_coverage_status": "PROVEN",
            "segment_count": 10,
            "comment_count": 5,
            "fetched_at": "2026-08-03T00:00:00+00:00",
            "private_result_path": f"videos/{video_id}/latest/",
        }

    monkeypatch.setattr(batch, "_fetch_one", fake_fetch_one)
    receipt, destination = batch.run_batch(
        {
            "request_id": "batch-proof",
            "video_urls": [batch.canonical_url(video_id) for video_id in video_ids],
            "comments": 5,
        },
        tmp_path,
        fast_cloud=True,
    )

    assert receipt["status"] == "PROVEN"
    assert receipt["coverage"]["exactly_once"] is True
    assert receipt["coverage"]["ordered_contiguous"] is True
    assert [item["index"] for item in receipt["results"]] == [1, 2]
    assert (destination / "batch-receipt.json").is_file()
    reader = json.loads(
        (destination / "batch-reader-manifest.json").read_text(encoding="utf-8")
    )
    assert len(reader["private_read_order"]) == 3


def test_catalog_only_batch_can_be_proven(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    channel = {
        "channel_id": "UC1234567890123456789012",
        "channel_title": "Example",
        "requested_reference": "@example",
        "status": "PROVEN",
        "video_count": 2,
        "unavailable_video_count": 0,
        "catalog_exhausted": True,
        "truncated_by_limit": False,
        "next_start_index": None,
        "private_result_path": "channels/UC1234567890123456789012/latest/",
        "local_result_path": "ignored",
    }
    monkeypatch.setattr(
        batch,
        "_resolve_sources",
        lambda _request, _key, _output: ([], [], [channel], 0),
    )

    receipt, destination = batch.run_batch(
        {
            "request_id": "channel-catalog-proof",
            "channel_url": "@example",
            "research_channel_videos": False,
        },
        tmp_path,
        youtube_api_key="test-key",
        fast_cloud=True,
    )

    assert receipt["status"] == "PROVEN"
    assert receipt["resolved_video_count"] == 0
    assert receipt["channel_catalog_status"] == "PROVEN"
    assert receipt["coverage"]["exactly_once"] is True
    reader = json.loads(
        (destination / "batch-reader-manifest.json").read_text(encoding="utf-8")
    )
    assert reader["private_read_order"][1].startswith("channels/")
