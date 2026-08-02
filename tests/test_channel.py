from __future__ import annotations

import json

import pytest

from aitubetranscript import channel


def test_parse_channel_reference_supports_ids_handles_and_urls() -> None:
    channel_id = "UC1234567890123456789012"
    assert channel.parse_channel_reference(channel_id) == ("id", channel_id)
    assert channel.parse_channel_reference("@example.channel") == (
        "forHandle",
        "@example.channel",
    )
    assert channel.parse_channel_reference(
        f"https://www.youtube.com/channel/{channel_id}"
    ) == ("id", channel_id)
    assert channel.parse_channel_reference(
        "https://www.youtube.com/@example.channel/videos"
    ) == ("forHandle", "@example.channel")


def test_duration_parsing_and_display() -> None:
    assert channel._iso8601_duration_seconds("PT15M33S") == 933
    assert channel._iso8601_duration_seconds("PT1H2M3S") == 3723
    assert channel._duration_display(933) == "15:33"
    assert channel._duration_display(3723) == "1:02:03"


def test_fetch_channel_catalog_lists_titles_dates_and_durations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            {
                "items": [
                    {
                        "id": "UC1234567890123456789012",
                        "snippet": {
                            "title": "Example Channel",
                            "description": "Description",
                            "customUrl": "@example",
                            "publishedAt": "2020-01-02T03:04:05Z",
                        },
                        "contentDetails": {
                            "relatedPlaylists": {"uploads": "UU1234567890123456789012"}
                        },
                        "statistics": {
                            "viewCount": "1000",
                            "subscriberCount": "25",
                            "videoCount": "2",
                        },
                    }
                ]
            },
            {
                "items": [
                    {
                        "snippet": {
                            "title": "First",
                            "publishedAt": "2026-08-02T10:00:00Z",
                        },
                        "contentDetails": {
                            "videoId": "AAAAAAAAAAA",
                            "videoPublishedAt": "2026-08-01T09:00:00Z",
                        },
                        "status": {"privacyStatus": "public"},
                    },
                    {
                        "snippet": {
                            "title": "Second",
                            "publishedAt": "2026-07-02T10:00:00Z",
                        },
                        "contentDetails": {
                            "videoId": "BBBBBBBBBBB",
                            "videoPublishedAt": "2026-07-01T09:00:00Z",
                        },
                        "status": {"privacyStatus": "public"},
                    },
                ]
            },
            {
                "items": [
                    {
                        "id": "AAAAAAAAAAA",
                        "snippet": {
                            "title": "First video",
                            "description": "A",
                            "publishedAt": "2026-08-01T09:00:00Z",
                            "liveBroadcastContent": "none",
                        },
                        "contentDetails": {"duration": "PT15M33S"},
                        "statistics": {
                            "viewCount": "123",
                            "likeCount": "12",
                            "commentCount": "3",
                        },
                        "status": {"privacyStatus": "public"},
                    },
                    {
                        "id": "BBBBBBBBBBB",
                        "snippet": {
                            "title": "Second video",
                            "description": "B",
                            "publishedAt": "2026-07-01T09:00:00Z",
                            "liveBroadcastContent": "none",
                        },
                        "contentDetails": {"duration": "PT1H2M3S"},
                        "statistics": {
                            "viewCount": "456",
                            "likeCount": "45",
                            "commentCount": "6",
                        },
                        "status": {"privacyStatus": "public"},
                    },
                ]
            },
        ]
    )
    monkeypatch.setattr(channel, "_fetch_json", lambda *_args, **_kwargs: next(responses))

    catalog = channel.fetch_channel_catalog("@example", "test-key", limit=10)

    assert catalog["status"] == "PROVEN"
    assert catalog["channel"]["title"] == "Example Channel"
    assert [video["title"] for video in catalog["videos"]] == [
        "First video",
        "Second video",
    ]
    assert catalog["videos"][0]["published_date"] == "2026-08-01"
    assert catalog["videos"][0]["duration_seconds"] == 933
    assert catalog["videos"][0]["duration_display"] == "15:33"
    assert catalog["videos"][1]["duration_display"] == "1:02:03"
    assert catalog["coverage"]["exactly_once"] is True


def test_write_channel_catalog_creates_human_and_machine_files(tmp_path) -> None:
    catalog = {
        "schema_version": "1.0",
        "status": "PROVEN",
        "fetched_at": "2026-08-03T00:00:00+00:00",
        "requested_reference": "@example",
        "channel": {
            "channel_id": "UC1234567890123456789012",
            "title": "Example Channel",
        },
        "selection": {
            "selected_count": 1,
            "catalog_exhausted": True,
            "truncated_by_limit": False,
            "next_start_index": None,
        },
        "unavailable_video_count": 0,
        "coverage": {
            "status": "PROVEN",
            "exactly_once": True,
            "missing_indices": [],
            "duplicate_indices": [],
            "unexpected_indices": [],
            "ordered_contiguous": True,
        },
        "videos": [
            {
                "index": 1,
                "channel_upload_index": 1,
                "video_id": "AAAAAAAAAAA",
                "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                "title": "First video",
                "published_at": "2026-08-01T09:00:00Z",
                "published_date": "2026-08-01",
                "duration": "PT15M33S",
                "duration_seconds": 933,
                "duration_display": "15:33",
                "view_count": 123,
            }
        ],
    }

    destination = channel.write_channel_catalog(catalog, tmp_path)

    assert (destination / "channel-videos.md").is_file()
    assert (destination / "channel-videos.jsonl").is_file()
    assert (destination / "channel-catalog.json").is_file()
    receipt = json.loads(
        (destination / "channel-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "PROVEN"
    assert receipt["video_count"] == 1
