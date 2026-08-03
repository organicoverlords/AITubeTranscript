from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aitubetranscript.legacy_split_migration import (
    _ensure_legacy_transcript_manifest,
)


def test_verified_legacy_monolithic_transcript_is_reconstructed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "videos" / "abcdefghijk" / "latest"
    source.mkdir(parents=True)
    transcript = b"# Transcript\n\nLegacy complete transcript.\n"
    (source / "transcript.md").write_bytes(transcript)
    digest = hashlib.sha256(transcript).hexdigest()
    receipt = {
        "video_id": "abcdefghijk",
        "transcript_status": "PROVEN",
        "segment_count": 154,
        "sha256": {"transcript.md": digest},
    }

    assert _ensure_legacy_transcript_manifest(source, receipt) is True
    manifest = json.loads(
        (source / "transcript-manifest.json").read_text(encoding="utf-8")
    )
    reader = json.loads(
        (source / "reader-manifest.json").read_text(encoding="utf-8")
    )
    migrated_receipt = json.loads(
        (source / "receipt.json").read_text(encoding="utf-8")
    )

    assert manifest["coverage"]["status"] == "PROVEN"
    assert manifest["coverage"]["exactly_once"] is True
    assert manifest["chunks"][0]["path"] == "chunks/001.md"
    assert manifest["chunks"][0]["last_segment"] == 154
    assert manifest["legacy_reconstruction"]["refetched"] is False
    assert (source / "chunks" / "001.md").read_bytes() == transcript
    assert reader["transcript"]["chunks"] == ["chunks/001.md"]
    assert migrated_receipt["transcript_coverage_status"] == "PROVEN"


def test_legacy_monolithic_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "videos" / "abcdefghijk" / "latest"
    source.mkdir(parents=True)
    (source / "transcript.md").write_text("changed", encoding="utf-8")
    receipt = {
        "video_id": "abcdefghijk",
        "transcript_status": "PROVEN",
        "segment_count": 1,
        "sha256": {"transcript.md": "0" * 64},
    }

    with pytest.raises(ValueError, match="hash mismatch"):
        _ensure_legacy_transcript_manifest(source, receipt)


def test_existing_proven_manifest_promotes_missing_receipt_coverage(
    tmp_path: Path,
) -> None:
    source = tmp_path / "videos" / "abcdefghijk" / "latest"
    source.mkdir(parents=True)
    (source / "transcript-manifest.json").write_text(
        json.dumps({"coverage": {"status": "PROVEN"}}),
        encoding="utf-8",
    )
    receipt = {
        "video_id": "abcdefghijk",
        "transcript_status": "PROVEN",
        "segment_count": 1,
    }

    assert _ensure_legacy_transcript_manifest(source, receipt) is False
    migrated_receipt = json.loads(
        (source / "receipt.json").read_text(encoding="utf-8")
    )
    assert migrated_receipt["transcript_coverage_status"] == "PROVEN"


def test_existing_unproven_manifest_does_not_invent_coverage(
    tmp_path: Path,
) -> None:
    source = tmp_path / "videos" / "abcdefghijk" / "latest"
    source.mkdir(parents=True)
    (source / "transcript-manifest.json").write_text(
        json.dumps({"coverage": {"status": "NOT_PROVEN"}}),
        encoding="utf-8",
    )
    receipt: dict[str, object] = {}

    assert _ensure_legacy_transcript_manifest(source, receipt) is False
    assert not (source / "receipt.json").exists()
