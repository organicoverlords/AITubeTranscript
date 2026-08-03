from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .volatile_store import purge_expired_overlays, rebuild_volatile_indexes


def maintain_volatile_store(
    root: Path, *, now: datetime | None = None
) -> dict[str, object]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    purge = purge_expired_overlays(root.resolve(), now=current)
    index = rebuild_volatile_indexes(root.resolve(), now=current)
    return {
        "schema_version": "1.0",
        "checked_at": current.isoformat().replace("+00:00", "Z"),
        "purge": purge,
        "index": index,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate and purge expired AITube volatile API overlays."
    )
    parser.add_argument("--volatile-root", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = maintain_volatile_store(args.volatile_root)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"PURGED_OVERLAYS={result['purge']['removed_count']}")
    print(f"VOLATILE_RECORDS={result['index']['records']}")
    print("VOLATILE_RETENTION_MAINTENANCE=PROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
