from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .storage_common import parse_datetime, read_json
from .volatile_store import evaluate_retention


def select_video_snapshot(
    durable_root: Path,
    video_id: str,
    *,
    volatile_root: Path | None = None,
    language: str | None = None,
    require_transcript: bool = True,
    min_comments: int = 0,
    max_api_age_days: int | None = None,
    prefer_source: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Select a snapshot by explicit requirements instead of a universal best score."""
    durable_root = durable_root.resolve()
    volatile_root = volatile_root.resolve() if volatile_root else None
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates = []

    for path in sorted(
        (durable_root / "videos" / video_id / "snapshots").glob(
            "*/snapshot-metadata.json"
        )
    ):
        durable = read_json(path)
        key = str(durable["snapshot_key"])
        overlay = _load_overlay(volatile_root, video_id, key)
        evaluation = _evaluate_candidate(
            durable,
            overlay,
            language=language,
            require_transcript=require_transcript,
            min_comments=min_comments,
            max_api_age_days=max_api_age_days,
            prefer_source=prefer_source,
            now=current,
        )
        candidates.append(evaluation)

    satisfied = [item for item in candidates if item["satisfies"]]
    if not satisfied:
        return {
            "schema_version": "1.0",
            "video_id": video_id,
            "selection_status": "UNSATISFIED",
            "requirements": _requirements(
                language,
                require_transcript,
                min_comments,
                max_api_age_days,
                prefer_source,
            ),
            "selected_snapshot": None,
            "candidate_count": len(candidates),
            "rejections": [
                {
                    "snapshot_key": item["snapshot_key"],
                    "reasons": item["rejection_reasons"],
                }
                for item in candidates
            ],
        }

    selected = max(satisfied, key=lambda item: item["score"])
    return {
        "schema_version": "1.0",
        "video_id": video_id,
        "selection_status": "SATISFIED",
        "requirements": _requirements(
            language,
            require_transcript,
            min_comments,
            max_api_age_days,
            prefer_source,
        ),
        "selected_snapshot": selected["durable_snapshot_path"],
        "selected_snapshot_key": selected["snapshot_key"],
        "reader_manifest_path": selected["reader_manifest_path"],
        "receipt_path": selected["receipt_path"],
        "api_overlay_path": selected["api_overlay_path"],
        "api_retention": selected["api_retention"],
        "evidence": selected["evidence"],
        "reasons": selected["selection_reasons"],
        "candidate_count": len(candidates),
    }


def _evaluate_candidate(
    durable: dict[str, Any],
    overlay: dict[str, Any] | None,
    *,
    language: str | None,
    require_transcript: bool,
    min_comments: int,
    max_api_age_days: int | None,
    prefer_source: str | None,
    now: datetime,
) -> dict[str, Any]:
    profile = durable.get("request_profile") or {}
    evidence = durable.get("evidence") or {}
    rejection_reasons = []
    selection_reasons = []

    transcript_proven = (
        evidence.get("transcript_status") == "PROVEN"
        and evidence.get("transcript_coverage_status") == "PROVEN"
    )
    if require_transcript and not transcript_proven:
        rejection_reasons.append("transcript proof is not complete")
    elif transcript_proven:
        selection_reasons.append("transcript coverage proven")

    if language and not _language_matches(profile.get("languages"), language):
        rejection_reasons.append(f"language {language!r} not matched")
    elif language:
        selection_reasons.append(f"language {language!r} matched")

    api_retention = {}
    comment_count = 0
    if overlay:
        api_retention = evaluate_retention(overlay.get("retention") or {}, now)
        comment_count = int(overlay.get("comment_count") or 0)
    if min_comments > 0:
        if not overlay:
            rejection_reasons.append("required API overlay is missing")
        elif api_retention.get("status") == "EXPIRED":
            rejection_reasons.append("API overlay is expired")
        elif comment_count < min_comments:
            rejection_reasons.append(
                f"only {comment_count} comments available; {min_comments} required"
            )
        else:
            selection_reasons.append(f"{comment_count} comments satisfy minimum")

    if max_api_age_days is not None:
        if not overlay:
            rejection_reasons.append("API age requirement needs an overlay")
        else:
            fetched = parse_datetime(overlay.get("fetched_at"))
            if fetched < now - timedelta(days=max_api_age_days):
                rejection_reasons.append(
                    f"API overlay is older than {max_api_age_days} days"
                )
            else:
                selection_reasons.append(
                    f"API overlay age is within {max_api_age_days} days"
                )

    source = str(profile.get("transcript_source") or "")
    source_preferred = bool(prefer_source and prefer_source.lower() in source.lower())
    if source_preferred:
        selection_reasons.append(f"preferred transcript source {prefer_source!r}")

    score = (
        1 if source_preferred else 0,
        1 if transcript_proven else 0,
        comment_count,
        str(durable.get("fetched_at") or ""),
        str(durable.get("bundle_sha256") or ""),
    )
    base = str(durable["snapshot_path"])
    return {
        "snapshot_key": durable["snapshot_key"],
        "durable_snapshot_path": base,
        "reader_manifest_path": base + "reader-manifest.json",
        "receipt_path": base + "receipt.json",
        "api_overlay_path": overlay.get("overlay_path") if overlay else None,
        "api_retention": api_retention,
        "evidence": evidence,
        "satisfies": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
        "selection_reasons": selection_reasons,
        "score": score,
    }


def _load_overlay(
    volatile_root: Path | None, video_id: str, snapshot_key: str
) -> dict[str, Any] | None:
    if not volatile_root:
        return None
    path = (
        volatile_root
        / "videos"
        / video_id
        / "overlays"
        / snapshot_key
        / "overlay-metadata.json"
    )
    return read_json(path) if path.is_file() else None


def _language_matches(stored: Any, requested: str) -> bool:
    if isinstance(stored, list):
        values = [str(item).strip().lower() for item in stored]
    else:
        values = [
            item.strip().lower()
            for item in str(stored or "").replace(",", " ").split()
        ]
    return requested.strip().lower() in values


def _requirements(
    language: str | None,
    require_transcript: bool,
    min_comments: int,
    max_api_age_days: int | None,
    prefer_source: str | None,
) -> dict[str, Any]:
    return {
        "language": language,
        "require_transcript": require_transcript,
        "min_comments": min_comments,
        "max_api_age_days": max_api_age_days,
        "prefer_source": prefer_source,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select an AITube snapshot by explicit evidence requirements."
    )
    parser.add_argument("video_id")
    parser.add_argument("--durable-root", required=True, type=Path)
    parser.add_argument("--volatile-root", type=Path)
    parser.add_argument("--language")
    parser.add_argument("--no-require-transcript", action="store_true")
    parser.add_argument("--min-comments", type=int, default=0)
    parser.add_argument("--max-api-age-days", type=int)
    parser.add_argument("--prefer-source")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = select_video_snapshot(
        args.durable_root,
        args.video_id,
        volatile_root=args.volatile_root,
        language=args.language,
        require_transcript=not args.no_require_transcript,
        min_comments=args.min_comments,
        max_api_age_days=args.max_api_age_days,
        prefer_source=args.prefer_source,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["selection_status"] == "SATISFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
