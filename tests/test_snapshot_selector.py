from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aitubetranscript.snapshot_selector import (
    SelectionRequirements,
    select_video_snapshot,
)


def _write_snapshot(
    vault: Path,
    key: str,
    *,
    fetched_at: str,
    comments: int,
    language: str = "en",
    transcript_source: str = "youtube-captions",
    delete_by: str = "2026-09-30T00:00:00Z",
) -> None:
    root = vault / "videos" / "abcdefghijk" / "snapshots" / key
    root.mkdir(parents=True)
    value = {
        "snapshot_key": key,
        "fetched_at": fetched_at,
        "request_profile": {
            "languages": language,
            "comments_requested": comments,
            "transcript_source": transcript_source,
        },
        "evidence": {
            "transcript_status": "PROVEN",
            "transcript_coverage_status": "PROVEN",
            "comments_status": "PROVEN" if comments else "NOT_PROVEN",
            "comments_coverage_status": "PROVEN" if comments else "NOT_APPLICABLE",
            "segment_count": 50,
            "comment_count": comments,
        },
        "retention": {
            "data_origin": "youtube-data-api-v3",
            "fetched_at": fetched_at,
            "refresh_due_at": "2026-09-20T00:00:00Z",
            "delete_or_refresh_by": delete_by,
            "status": "CURRENT",
        },
    }
    (root / "snapshot-metadata.json").write_text(json.dumps(value), encoding="utf-8")


def test_selector_prefers_snapshot_that_satisfies_comment_requirement(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "newer-10",
        fetched_at="2026-08-03T00:00:00Z",
        comments=10,
    )
    _write_snapshot(
        tmp_path,
        "older-100",
        fetched_at="2026-08-02T00:00:00Z",
        comments=100,
    )

    result = select_video_snapshot(
        tmp_path,
        "abcdefghijk",
        SelectionRequirements(language="en", min_comments=100),
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert result["selection_status"] == "SATISFIED"
    assert result["snapshot_key"] == "older-100"


def test_selector_rejects_expired_snapshot(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "expired",
        fetched_at="2026-07-01T00:00:00Z",
        comments=100,
        delete_by="2026-07-31T00:00:00Z",
    )

    result = select_video_snapshot(
        tmp_path,
        "abcdefghijk",
        SelectionRequirements(language="en", min_comments=100),
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert result["selection_status"] == "UNSATISFIED"
