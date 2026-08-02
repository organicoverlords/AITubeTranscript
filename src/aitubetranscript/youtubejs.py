from __future__ import annotations

import json
import shutil
import subprocess
from importlib.resources import as_file, files
from typing import Any


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
