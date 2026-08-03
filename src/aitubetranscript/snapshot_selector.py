from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SelectionRequirements:
    language: str | None = None
    require_transcript: bool = True
    min_comments: int = 0
    max_api_age_days: int | None = None
    prefer_sources: tuple[str, ...] = ()


def select_video_snapshot(
    vault: Path,
    video_id: str,
    requirements: SelectionRequirements,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot_root = vault / "videos" / video_id / "snapshots"
    candidates = []
    for metadata_path in sorted(snapshot_root.glob("*/snapshot-metadata.json")):
        metadata = _read_json(metadata_path)
        result = _evaluate(metadata, requirements, now)
        if result["satisfied"]:
            candidates.append(result)

    if not candidates:
        return {
            "schema_version": "1.0",
            "video_id": video_id,
            "selection_status": "UNSATISFIED",
            "requirements": _requirements_dict(requirements),
            "selected_snapshot": None,
            "reasons": ["no stored snapshot satisfies every requirement"],
        }

    selected = max(candidates, key=lambda item: item["score"])
    metadata = selected["metadata"]
    snapshot_key = str(metadata["snapshot_key"])
    base = f"videos/{video_id}/snapshots/{snapshot_key}/"
    return {
        "schema_version": "1.0",
        "video_id": video_id,
        "selection_status": "SATISFIED",
        "requirements": _requirements_dict(requirements),
        "selected_snapshot": base,
        "snapshot_key": snapshot_key,
        "receipt_path": base + "receipt.json",
        "reader_manifest_path": base + "reader-manifest.json",
        "request_profile": metadata.get("request_profile") or {},
        "evidence": metadata.get("evidence") or {},
        "retention": metadata.get("retention") or {},
        "score": list(selected["score"]),
        "reasons": selected["reasons"],
    }


def _evaluate(
    metadata: dict[str, Any],
    requirements: SelectionRequirements,
    now: datetime,
) -> dict[str, Any]:
    profile = metadata.get("request_profile") or {}
    evidence = metadata.get("evidence") or {}
    retention = metadata.get("retention") or {}
    reasons: list[str] = []

    transcript_proven = (
        evidence.get("transcript_status") == "PROVEN"
        and evidence.get("transcript_coverage_status") == "PROVEN"
    )
    if requirements.require_transcript and not transcript_proven:
        return {"satisfied": False}
    if transcript_proven:
        reasons.append("transcript coverage proven")

    requested_language = (requirements.language or "").strip().lower()
    stored_languages = _stored_languages(profile)
    if requested_language and requested_language not in stored_languages:
        return {"satisfied": False}
    if requested_language:
        reasons.append(f"language matched: {requested_language}")

    comment_count = int(evidence.get("comment_count") or 0)
    comments_proven = (
        evidence.get("comments_status") == "PROVEN"
        and evidence.get("comments_coverage_status") == "PROVEN"
    )
    if requirements.min_comments > 0:
        if not comments_proven or comment_count < requirements.min_comments:
            return {"satisfied": False}
        reasons.append(f"proven comments satisfy minimum: {comment_count}")

    retention_state = _retention_state(retention, now)
    if retention_state == "EXPIRED":
        return {"satisfied": False}
    if requirements.max_api_age_days is not None:
        fetched_at = _parse_datetime(retention.get("fetched_at") or metadata.get("fetched_at"))
        age_days = (now - fetched_at).total_seconds() / 86400
        if age_days > requirements.max_api_age_days:
            return {"satisfied": False}
        reasons.append(f"API age within {requirements.max_api_age_days} days")

    transcript_source = str(profile.get("transcript_source") or "")
    source_rank = 0
    for index, preferred in enumerate(requirements.prefer_sources):
        if preferred.lower() in transcript_source.lower():
            source_rank = len(requirements.prefer_sources) - index
            reasons.append(f"preferred transcript source matched: {preferred}")
            break

    fetched_at = _parse_datetime(metadata.get("fetched_at"))
    score = (
        1 if transcript_proven else 0,
        1 if comments_proven else 0,
        comment_count,
        source_rank,
        int(fetched_at.timestamp()),
    )
    return {
        "satisfied": True,
        "metadata": metadata,
        "score": score,
        "reasons": reasons,
    }


def _stored_languages(profile: dict[str, Any]) -> set[str]:
    value = profile.get("languages") or profile.get("language") or ""
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return {item.strip().lower() for item in str(value).split(",") if item.strip()}


def _retention_state(retention: dict[str, Any], now: datetime) -> str:
    deadline = retention.get("delete_or_refresh_by")
    if deadline and now >= _parse_datetime(deadline):
        return "EXPIRED"
    refresh = retention.get("refresh_due_at")
    if refresh and now >= _parse_datetime(refresh):
        return "REFRESH_DUE"
    return str(retention.get("status") or "CURRENT")


def _requirements_dict(value: SelectionRequirements) -> dict[str, Any]:
    return {
        "language": value.language,
        "require_transcript": value.require_transcript,
        "min_comments": value.min_comments,
        "max_api_age_days": value.max_api_age_days,
        "prefer_sources": list(value.prefer_sources),
    }


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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select a stored snapshot by requirements.")
    parser.add_argument("vault", type=Path)
    parser.add_argument("video_id")
    parser.add_argument("--language")
    parser.add_argument("--no-require-transcript", action="store_true")
    parser.add_argument("--min-comments", type=int, default=0)
    parser.add_argument("--max-api-age-days", type=int)
    parser.add_argument("--prefer-source", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = select_video_snapshot(
        args.vault,
        args.video_id,
        SelectionRequirements(
            language=args.language,
            require_transcript=not args.no_require_transcript,
            min_comments=max(0, args.min_comments),
            max_api_age_days=args.max_api_age_days,
            prefer_sources=tuple(args.prefer_source),
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["selection_status"] == "SATISFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
