from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from .youtube import canonical_url, extract_video_id

_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/\S+",
    re.IGNORECASE,
)
_ALLOWED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def resolve_request(event: dict, allow_public: bool = False) -> dict[str, str]:
    issue = event.get("issue") or {}
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    association = str(issue.get("author_association") or "NONE").upper()

    if issue and not title.lower().startswith("[fetch]"):
        raise ValueError("Issue title must start with [fetch]")
    if issue and not allow_public and association not in _ALLOWED_ASSOCIATIONS:
        raise PermissionError(
            "Public issue execution is disabled. Fork the repository or set "
            "ALLOW_PUBLIC_REQUESTS=true."
        )

    candidate = _first_url(title + "\n" + body)
    if not candidate:
        candidate = str((event.get("inputs") or {}).get("video_url") or "").strip()
    video_id = extract_video_id(candidate)

    inputs = event.get("inputs") or {}
    return {
        "video_url": canonical_url(video_id),
        "video_id": video_id,
        "languages": str(inputs.get("languages") or "en"),
        "comments": str(inputs.get("comments") or "100"),
        "whisper": str(inputs.get("whisper") or "false").lower(),
    }


def _first_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    return match.group(0).rstrip(").,]>\"'") if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    event = json.loads(args.event.read_text(encoding="utf-8"))
    allow_public = os.getenv("ALLOW_PUBLIC_REQUESTS", "false").lower() == "true"
    request = resolve_request(event, allow_public=allow_public)
    output = args.github_output or (
        Path(os.environ["GITHUB_OUTPUT"]) if os.getenv("GITHUB_OUTPUT") else None
    )
    if output:
        with output.open("a", encoding="utf-8") as handle:
            for key, value in request.items():
                handle.write(f"{key}={value}\n")
    else:
        print(json.dumps(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
