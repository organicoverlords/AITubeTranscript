from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import ResearchBundle


def write_bundle(bundle: ResearchBundle, output_root: Path) -> Path:
    destination = output_root / bundle.video_id
    destination.mkdir(parents=True, exist_ok=True)

    transcript_text = _transcript_text(bundle)
    transcript_markdown = _transcript_markdown(bundle)
    description_markdown = _description_markdown(bundle)
    comments_markdown = _comments_markdown(bundle)

    files: dict[str, str] = {
        "result.json": json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2) + "\n",
        "transcript.txt": transcript_text,
        "transcript.md": transcript_markdown,
        "description.md": description_markdown,
        "comments.md": comments_markdown,
    }
    for name, content in files.items():
        (destination / name).write_text(content, encoding="utf-8")

    receipt = {
        "schema_version": "1.0",
        "video_id": bundle.video_id,
        "canonical_url": bundle.canonical_url,
        "fetched_at": bundle.fetched_at,
        "transcript_status": (
            "PROVEN" if bundle.transcript and bundle.transcript.segments else "NOT_PROVEN"
        ),
        "comments_status": "PROVEN" if bundle.comments else "NOT_PROVEN",
        "transcript_source": bundle.transcript.source if bundle.transcript else None,
        "segment_count": len(bundle.transcript.segments) if bundle.transcript else 0,
        "comment_count": len(bundle.comments),
        "warnings": bundle.warnings,
        "attempts": bundle.attempts,
        "sha256": {
            name: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for name, content in files.items()
        },
    }
    (destination / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def _transcript_text(bundle: ResearchBundle) -> str:
    if not bundle.transcript:
        return ""
    return "\n".join(segment.text for segment in bundle.transcript.segments) + "\n"


def _transcript_markdown(bundle: ResearchBundle) -> str:
    title = bundle.metadata.get("title") or bundle.video_id
    source = bundle.transcript.source if bundle.transcript else "none"
    lines = [f"# Transcript: {title}", "", f"Source: `{source}`", ""]
    if not bundle.transcript:
        lines.append("No transcript was retrieved.")
    else:
        for segment in bundle.transcript.segments:
            lines.append(f"**[{_timestamp(segment.start)}]** {segment.text}")
    return "\n\n".join(lines) + "\n"


def _description_markdown(bundle: ResearchBundle) -> str:
    title = bundle.metadata.get("title") or bundle.video_id
    description = bundle.metadata.get("description") or "No description was retrieved."
    return f"# Description: {title}\n\n{description}\n"


def _comments_markdown(bundle: ResearchBundle) -> str:
    title = bundle.metadata.get("title") or bundle.video_id
    lines = [f"# Comments: {title}", ""]
    if not bundle.comments:
        lines.append("No comments were retrieved.")
    else:
        for index, comment in enumerate(bundle.comments, start=1):
            author = comment.author or "Unknown author"
            likes = f" · {comment.like_count} likes" if comment.like_count is not None else ""
            lines.extend([f"## {index}. {author}{likes}", "", comment.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
