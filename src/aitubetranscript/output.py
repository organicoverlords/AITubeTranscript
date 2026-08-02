from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .models import ResearchBundle

CHUNK_TARGET_UTF8_BYTES = 10_000
CHUNK_MAX_SEGMENTS = 40


def write_bundle(bundle: ResearchBundle, output_root: Path) -> Path:
    destination = output_root / bundle.video_id
    destination.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(destination / "chunks", ignore_errors=True)

    transcript_records = _transcript_records(bundle)
    transcript_jsonl = _transcript_jsonl(transcript_records)
    chunk_files, chunk_metadata = _transcript_chunks(bundle, transcript_records)
    transcript_manifest = _transcript_manifest(
        bundle,
        transcript_records,
        transcript_jsonl,
        chunk_metadata,
    )

    files: dict[str, str] = {
        "result.json": json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2) + "\n",
        "transcript.txt": _transcript_text(bundle),
        "transcript.md": _transcript_markdown(bundle),
        "transcript.jsonl": transcript_jsonl,
        "transcript-manifest.json": (
            json.dumps(transcript_manifest, ensure_ascii=False, indent=2) + "\n"
        ),
        "description.md": _description_markdown(bundle),
        "comments.md": _comments_markdown(bundle),
        **chunk_files,
    }
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    coverage = transcript_manifest["coverage"]
    receipt = {
        "schema_version": "1.1",
        "video_id": bundle.video_id,
        "canonical_url": bundle.canonical_url,
        "fetched_at": bundle.fetched_at,
        "transcript_status": (
            "PROVEN" if bundle.transcript and bundle.transcript.segments else "NOT_PROVEN"
        ),
        "transcript_coverage_status": coverage["status"],
        "transcript_manifest": "transcript-manifest.json",
        "transcript_chunk_count": len(chunk_metadata),
        "comments_status": "PROVEN" if bundle.comments else "NOT_PROVEN",
        "transcript_source": bundle.transcript.source if bundle.transcript else None,
        "segment_count": len(bundle.transcript.segments) if bundle.transcript else 0,
        "comment_count": len(bundle.comments),
        "warnings": bundle.warnings,
        "attempts": bundle.attempts,
        "sha256": {
            name: _sha256_text(content)
            for name, content in sorted(files.items())
        },
    }
    (destination / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _transcript_records(bundle: ResearchBundle) -> list[dict[str, Any]]:
    if not bundle.transcript:
        return []

    records = []
    for index, segment in enumerate(bundle.transcript.segments, start=1):
        records.append(
            {
                "index": index,
                "start": segment.start,
                "duration": segment.duration,
                "end": segment.end,
                "timestamp": _timestamp_milliseconds(segment.start),
                "text": segment.text,
                "text_sha256": _sha256_text(segment.text),
            }
        )
    return records


def _transcript_jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
        for record in records
    )


def _transcript_chunks(
    bundle: ResearchBundle,
    records: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    grouped = _group_transcript_records(records)
    if not grouped:
        return {}, []

    width = max(3, len(str(len(grouped))))
    files: dict[str, str] = {}
    metadata: list[dict[str, Any]] = []
    for chunk_number, chunk_records in enumerate(grouped, start=1):
        path = f"chunks/{chunk_number:0{width}d}.md"
        content = _chunk_markdown(
            bundle,
            chunk_records,
            chunk_number=chunk_number,
            chunk_count=len(grouped),
        )
        content_bytes = len(content.encode("utf-8"))
        files[path] = content
        metadata.append(
            {
                "path": path,
                "chunk_number": chunk_number,
                "first_segment": chunk_records[0]["index"],
                "last_segment": chunk_records[-1]["index"],
                "segment_count": len(chunk_records),
                "utf8_bytes": content_bytes,
                "sha256": _sha256_text(content),
                "oversized_single_segment": (
                    len(chunk_records) == 1
                    and content_bytes > CHUNK_TARGET_UTF8_BYTES
                ),
            }
        )
    return files, metadata


def _group_transcript_records(
    records: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_bytes = 0

    for record in records:
        estimated = len(_segment_markdown(record).encode("utf-8"))
        at_segment_limit = len(current) >= CHUNK_MAX_SEGMENTS
        at_byte_limit = current_bytes + estimated > CHUNK_TARGET_UTF8_BYTES
        if current and (at_segment_limit or at_byte_limit):
            groups.append(current)
            current = []
            current_bytes = 0
        current.append(record)
        current_bytes += estimated

    if current:
        groups.append(current)
    return groups


def _transcript_manifest(
    bundle: ResearchBundle,
    records: list[dict[str, Any]],
    transcript_jsonl: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = list(range(1, len(records) + 1))
    represented: list[int] = []
    for chunk in chunks:
        represented.extend(
            range(chunk["first_segment"], chunk["last_segment"] + 1)
        )

    counts = Counter(represented)
    expected_set = set(expected)
    missing = [index for index in expected if counts[index] == 0]
    duplicates = [index for index in expected if counts[index] > 1]
    unexpected = sorted(index for index in counts if index not in expected_set)
    ordered = represented == expected
    exactly_once = not missing and not duplicates and not unexpected and ordered
    if records:
        coverage_status = "PROVEN" if exactly_once else "REJECTED"
    else:
        coverage_status = "NOT_APPLICABLE"

    return {
        "schema_version": "1.0",
        "video_id": bundle.video_id,
        "canonical_url": bundle.canonical_url,
        "fetched_at": bundle.fetched_at,
        "transcript_source": bundle.transcript.source if bundle.transcript else None,
        "segment_count": len(records),
        "chunk_count": len(chunks),
        "transcript_jsonl": {
            "path": "transcript.jsonl",
            "line_count": len(records),
            "utf8_bytes": len(transcript_jsonl.encode("utf-8")),
            "sha256": _sha256_text(transcript_jsonl),
        },
        "chunking": {
            "target_max_utf8_bytes": CHUNK_TARGET_UTF8_BYTES,
            "max_segments": CHUNK_MAX_SEGMENTS,
            "whole_segments_only": True,
        },
        "chunks": chunks,
        "coverage": {
            "status": coverage_status,
            "expected_first_segment": 1 if records else None,
            "expected_last_segment": len(records) if records else None,
            "represented_segment_count": len(represented),
            "ranges": [
                [chunk["first_segment"], chunk["last_segment"]]
                for chunk in chunks
            ],
            "missing_indices": missing,
            "duplicate_indices": duplicates,
            "unexpected_indices": unexpected,
            "ordered_contiguous": ordered,
            "exactly_once": exactly_once,
        },
    }


def _chunk_markdown(
    bundle: ResearchBundle,
    records: list[dict[str, Any]],
    *,
    chunk_number: int,
    chunk_count: int,
) -> str:
    title = bundle.metadata.get("title") or bundle.video_id
    source = bundle.transcript.source if bundle.transcript else "none"
    first_index = records[0]["index"]
    last_index = records[-1]["index"]
    lines = [
        f"# Transcript chunk {chunk_number:03d}/{chunk_count:03d}: {title}",
        "",
        f"- Video ID: `{bundle.video_id}`",
        f"- Source: `{source}`",
        f"- Segment range: `{first_index}-{last_index}`",
        f"- Segment count: `{len(records)}`",
        "",
    ]
    for record in records:
        lines.append(_segment_markdown(record).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _segment_markdown(record: dict[str, Any]) -> str:
    return (
        f"## Segment {record['index']:06d} — {record['timestamp']}\n\n"
        f"- Start: `{record['start']}`\n"
        f"- Duration: `{record['duration']}`\n"
        f"- End: `{record['end']}`\n"
        f"- Text SHA-256: `{record['text_sha256']}`\n\n"
        f"{record['text']}\n"
    )


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


def _timestamp_milliseconds(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
