from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .storage_common import read_json

MEMORY_CONTRACT_VERSION = "2026-08-05-v1"
MINIMUM_SCHEMA_MAJOR = 3


def _major(value: Any) -> int | None:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def check_memory_contract(
    durable_root: Path,
    volatile_root: Path,
    *,
    saved_contract_version: str | None = None,
) -> dict[str, Any]:
    """Validate the live split-memory layout and detect stale saved GPT routing rules."""
    durable_root = durable_root.resolve()
    volatile_root = volatile_root.resolve()
    durable_path = durable_root / "memory" / "bank-manifest.json"
    volatile_path = volatile_root / "memory" / "bank-manifest.json"
    failures: list[str] = []

    durable = read_json(durable_path) if durable_path.is_file() else None
    volatile = read_json(volatile_path) if volatile_path.is_file() else None
    if durable is None:
        failures.append("DURABLE_MEMORY_MANIFEST_MISSING")
    if volatile is None:
        failures.append("VOLATILE_MEMORY_MANIFEST_MISSING")

    if durable is not None:
        if _major(durable.get("schema_version")) is None or _major(
            durable.get("schema_version")
        ) < MINIMUM_SCHEMA_MAJOR:
            failures.append("DURABLE_MEMORY_SCHEMA_UNSUPPORTED")
        if durable.get("storage_class") != "DURABLE_POINTER_INDEX":
            failures.append("DURABLE_MEMORY_STORAGE_CLASS_INVALID")
        if durable.get("volatile_branch") != "aitube-volatile":
            failures.append("DURABLE_VOLATILE_BRANCH_LINK_INVALID")

    if volatile is not None:
        if _major(volatile.get("schema_version")) is None or _major(
            volatile.get("schema_version")
        ) < MINIMUM_SCHEMA_MAJOR:
            failures.append("VOLATILE_MEMORY_SCHEMA_UNSUPPORTED")
        if volatile.get("storage_class") != "VOLATILE_API_MEMORY_INDEX":
            failures.append("VOLATILE_MEMORY_STORAGE_CLASS_INVALID")
        if volatile.get("durable_branch") != "aitube-durable":
            failures.append("VOLATILE_DURABLE_BRANCH_LINK_INVALID")

    live_valid = not failures
    stale_reasons: list[str] = []
    if live_valid and saved_contract_version and saved_contract_version != MEMORY_CONTRACT_VERSION:
        stale_reasons.append("SAVED_GPT_CONTRACT_VERSION_STALE")
    stale = bool(stale_reasons)
    if not live_valid:
        status = "MEMORY_CONTRACT_INVALID"
    elif stale:
        status = "MEMORY_CONTRACT_STALE"
    else:
        status = "MEMORY_CONTRACT_CURRENT"

    return {
        "schema_version": "1.0",
        "memory_contract_version": MEMORY_CONTRACT_VERSION,
        "saved_contract_version": saved_contract_version,
        "status": status,
        "live_layout_valid": live_valid,
        "use_live_layout_even_when_saved_memory_is_stale": live_valid,
        "canonical": {
            "request_branch": "request/aitube-live",
            "request_file": "aitube-requests/current.json",
            "durable_branch": "aitube-durable",
            "volatile_branch": "aitube-volatile",
            "legacy_branch": "aitube-results",
            "legacy_role": "MIGRATION_OR_EXPLICIT_RECOVERY_ONLY",
            "durable_exact_video_lookup": "memory/by-video-id/<VIDEO_ID>.json",
            "volatile_video_index": "memory/video-index.jsonl",
            "volatile_retention_manifest": "retention/manifest.json",
        },
        "durable_manifest_path": str(durable_path),
        "volatile_manifest_path": str(volatile_path),
        "durable_manifest": durable,
        "volatile_manifest": volatile,
        "failure_codes": failures,
        "stale_reasons": stale_reasons,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the live AITube split memory contract and detect stale GPT routing."
    )
    parser.add_argument("--durable-root", required=True, type=Path)
    parser.add_argument("--volatile-root", required=True, type=Path)
    parser.add_argument("--saved-contract-version")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = check_memory_contract(
        args.durable_root,
        args.volatile_root,
        saved_contract_version=args.saved_contract_version,
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")
    if result["status"] == "MEMORY_CONTRACT_INVALID":
        return 2
    if result["status"] == "MEMORY_CONTRACT_STALE":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
