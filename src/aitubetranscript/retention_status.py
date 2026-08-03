from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


API_STATES = {"CURRENT", "REFRESH_DUE", "EXPIRED", "PURGE_REQUIRED"}


def evaluate_retention(vault: Path, *, now: datetime | None = None) -> dict[str, Any]:
    vault = vault.resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    counts: Counter[str] = Counter()
    changed = 0
    records = []

    for path in sorted((vault / "retention").glob("*/*/*.json")):
        value = _read_json(path)
        retention = value.get("retention") or {}
        state = retention_state(retention, now)
        counts[state] += 1
        records.append((path, value, state))
        if retention.get("status") != state:
            retention["status"] = state
            value["retention"] = retention
            _write_json(path, value)
            changed += 1

    deadlines = [
        value.get("retention", {}).get("delete_or_refresh_by")
        for _, value, _ in records
        if value.get("retention", {}).get("delete_or_refresh_by")
    ]
    manifest = {
        "schema_version": "1.1",
        "updated_at": _iso(now),
        "record_count": len(records),
        "api_record_count": sum(
            1
            for _, value, _ in records
            if value.get("retention", {}).get("data_origin")
            == "youtube-data-api-v3"
        ),
        "state_counts": dict(sorted(counts.items())),
        "records_changed": changed,
        "next_delete_or_refresh_by": min(deadlines) if deadlines else None,
        "policy": {
            "non_authorized_api_data": "REFRESH_OR_DELETE_WITHIN_30_DAYS",
            "transcripts_and_internal_provenance": "SEPARATELY_CLASSIFIED",
        },
    }
    _write_json(vault / "retention" / "manifest.json", manifest)
    return manifest


def retention_state(retention: dict[str, Any], now: datetime) -> str:
    if retention.get("data_origin") != "youtube-data-api-v3":
        return str(retention.get("status") or "RETAIN")
    delete_by = retention.get("delete_or_refresh_by")
    if delete_by and now >= _parse_datetime(delete_by):
        return "PURGE_REQUIRED"
    refresh_due = retention.get("refresh_due_at")
    if refresh_due and now >= _parse_datetime(refresh_due):
        return "REFRESH_DUE"
    return "CURRENT"


def _parse_datetime(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate AITube retention records.")
    parser.add_argument("vault", type=Path)
    args = parser.parse_args(argv)
    result = evaluate_retention(args.vault)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 3 if result["state_counts"].get("PURGE_REQUIRED", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
