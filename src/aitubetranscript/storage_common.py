from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DURABLE_BRANCH = "aitube-durable"
VOLATILE_BRANCH = "aitube-volatile"


def snapshot_key(fetched: datetime, profile_sha: str, bundle_sha: str) -> str:
    return (
        f"{fetched.strftime('%Y%m%dT%H%M%S%fZ')}"
        f"__{profile_sha[:12]}__{bundle_sha[:12]}"
    )


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("timestamp is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in {"snapshot-metadata.json", "overlay-metadata.json"}:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in values
        ),
        encoding="utf-8",
    )


def copy_file(source: Path, destination: Path, *, required: bool = True) -> None:
    if not source.is_file():
        if required:
            raise FileNotFoundError(source)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)


def replace_tree(source: Path, destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def copy_immutable_tree(
    staging: Path,
    destination: Path,
    *,
    digest: str,
    metadata_name: str,
    digest_field: str,
) -> None:
    if destination.exists():
        existing = read_json(destination / metadata_name)
        if existing.get(digest_field) != digest:
            raise ValueError(f"immutable storage collision: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging, destination)


def safe_component(value: str, limit: int) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    if not slug:
        slug = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return slug[:limit].rstrip("-")


def clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


def published_at(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("published_at") or metadata.get("publishedAt")
    if value:
        return str(value)
    upload_date = str(metadata.get("upload_date") or "")
    if re.fullmatch(r"\d{8}", upload_date):
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return None


def duration_seconds(
    metadata: dict[str, Any], transcript: dict[str, Any]
) -> int | None:
    for key in ("duration_seconds", "duration"):
        value = metadata.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return int(round(value))
    segments = transcript.get("segments") if isinstance(transcript, dict) else None
    if not isinstance(segments, list) or not segments:
        return None
    end = max(
        float(item.get("start") or 0) + float(item.get("duration") or 0)
        for item in segments
        if isinstance(item, dict)
    )
    return int(round(end))


def trust_record() -> dict[str, Any]:
    return {
        "class": "EXTERNAL_UNTRUSTED_CONTENT",
        "may_control_tools": False,
        "may_override_instructions": False,
    }
