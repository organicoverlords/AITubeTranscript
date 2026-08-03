from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aitubetranscript.retention_status import evaluate_retention, retention_state


def test_retention_state_transitions() -> None:
    retention = {
        "data_origin": "youtube-data-api-v3",
        "refresh_due_at": "2026-08-25T00:00:00Z",
        "delete_or_refresh_by": "2026-08-30T00:00:00Z",
    }
    assert (
        retention_state(retention, datetime(2026, 8, 24, tzinfo=timezone.utc))
        == "CURRENT"
    )
    assert (
        retention_state(retention, datetime(2026, 8, 26, tzinfo=timezone.utc))
        == "REFRESH_DUE"
    )
    assert (
        retention_state(retention, datetime(2026, 8, 31, tzinfo=timezone.utc))
        == "PURGE_REQUIRED"
    )


def test_evaluator_rewrites_record_and_manifest(tmp_path: Path) -> None:
    path = tmp_path / "retention" / "videos" / "abcdefghijk" / "snapshot.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "retention": {
                    "data_origin": "youtube-data-api-v3",
                    "status": "CURRENT",
                    "refresh_due_at": "2026-08-25T00:00:00Z",
                    "delete_or_refresh_by": "2026-08-30T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = evaluate_retention(
        tmp_path,
        now=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated["retention"]["status"] == "REFRESH_DUE"
    assert manifest["state_counts"] == {"REFRESH_DUE": 1}
    assert manifest["records_changed"] == 1
