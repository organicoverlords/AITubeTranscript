from __future__ import annotations

import json
import shutil
import subprocess
from importlib.resources import as_file, files
from typing import Any

from .models import CommentData, ResearchBundle


def enrich_bundle_with_youtubejs(
    bundle: ResearchBundle,
    comment_limit: int,
) -> None:
    """Fill missing public metadata/comments using YouTube.js when Deno is available."""
    needs_description = not bundle.metadata.get("description")
    needs_comments = comment_limit > 0 and not bundle.comments
    if not needs_description and not needs_comments:
        return

    metadata, raw_comments = fetch_youtubejs_data(
        bundle.video_id,
        comment_limit if needs_comments else 0,
        bundle.attempts,
    )
    for key, value in metadata.items():
        if value not in (None, "", []) and not bundle.metadata.get(key):
            bundle.metadata[key] = value

    if needs_comments and raw_comments:
        bundle.comments = [
            CommentData(
                author=_optional_text(item.get("author")),
                text=str(item.get("text") or "").strip(),
                like_count=_optional_int(item.get("like_count")),
                timestamp=None,
                parent=_optional_text(item.get("parent")),
            )
            for item in raw_comments[:comment_limit]
            if str(item.get("text") or "").strip()
        ]

    if bundle.comments:
        bundle.warnings = [
            warning
            for warning in bundle.warnings
            if not warning.startswith("No comments were returned")
        ]


def fetch_youtubejs_data(
    video_id: str,
    comment_limit: int,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Use YouTube.js through Deno when direct Python extractors are cloud-blocked."""
    deno = shutil.which("deno")
    if not deno:
        attempts.append(
            {
                "source": "YouTube.js InnerTube",
                "ok": False,
                "error": "Deno is not installed",
            }
        )
        return {}, []

    resource = files("aitubetranscript").joinpath("youtubejs.ts")
    try:
        with as_file(resource) as script_path:
            process = subprocess.run(
                [
                    deno,
                    "run",
                    "--quiet",
                    "-A",
                    str(script_path),
                    video_id,
                    str(max(0, comment_limit)),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=90,
            )
    except subprocess.TimeoutExpired:
        attempts.append(
            {
                "source": "YouTube.js InnerTube",
                "ok": False,
                "error": "timed out after 90 seconds",
            }
        )
        return {}, []
    except Exception as exc:
        attempts.append(
            {"source": "YouTube.js InnerTube", "ok": False, "error": str(exc)}
        )
        return {}, []

    if process.returncode != 0:
        error = process.stderr.strip() or f"Deno exited with {process.returncode}"
        attempts.append(
            {"source": "YouTube.js InnerTube", "ok": False, "error": error[-2000:]}
        )
        return {}, []

    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        attempts.append(
            {
                "source": "YouTube.js InnerTube",
                "ok": False,
                "error": f"invalid JSON: {exc}",
            }
        )
        return {}, []

    metadata = payload.get("metadata") if isinstance(payload, dict) else {}
    comments = payload.get("comments") if isinstance(payload, dict) else []
    warnings = payload.get("warnings") if isinstance(payload, dict) else []
    metadata = metadata if isinstance(metadata, dict) else {}
    comments = comments if isinstance(comments, list) else []
    warnings = warnings if isinstance(warnings, list) else []

    attempts.append(
        {
            "source": "YouTube.js InnerTube",
            "ok": bool(metadata.get("description") or comments),
            "metadata": bool(metadata),
            "comment_count": len(comments),
            "warnings": [str(item) for item in warnings],
        }
    )
    return metadata, comments


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
