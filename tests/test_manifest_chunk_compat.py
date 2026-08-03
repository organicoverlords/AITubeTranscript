from __future__ import annotations

from pathlib import Path

import pytest

from aitubetranscript.durable_store import _manifest_chunks


def test_manifest_chunks_accepts_structured_entries(tmp_path: Path) -> None:
    manifest = {
        "chunks": [
            {
                "path": "chunks/001.md",
                "chunk_number": 1,
                "first_segment": 1,
                "last_segment": 14,
            },
            {"file": "chunks/002.md"},
            "chunks/003.md",
        ]
    }

    assert _manifest_chunks(tmp_path, manifest) == [
        "chunks/001.md",
        "chunks/002.md",
        "chunks/003.md",
    ]


def test_manifest_chunks_rejects_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsafe transcript chunk path"):
        _manifest_chunks(tmp_path, {"chunks": [{"path": "../secret.txt"}]})


def test_manifest_chunks_rejects_structured_entry_without_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="has no path"):
        _manifest_chunks(tmp_path, {"chunks": [{"chunk_number": 1}]})
