import hashlib
import json
import re

from aitubetranscript.models import ResearchBundle, TranscriptData, TranscriptSegment
from aitubetranscript.output import write_bundle


def _bundle(segments):
    transcript = None
    if segments is not None:
        transcript = TranscriptData(
            source="test",
            language="English",
            language_code="en",
            is_generated=False,
            segments=segments,
        )
    return ResearchBundle(
        schema_version="1.0",
        fetched_at="2026-08-02T00:00:00+00:00",
        video_id="x8W_S9zmodk",
        canonical_url="https://www.youtube.com/watch?v=x8W_S9zmodk",
        metadata={"title": "Test", "description": "Desc"},
        transcript=transcript,
        comments=[],
        warnings=[],
        attempts=[],
    )


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_bundle(tmp_path):
    bundle = _bundle(
        [TranscriptSegment(text="Hello", start=1.0, duration=2.0)]
    )
    destination = write_bundle(bundle, tmp_path)
    receipt = json.loads((destination / "receipt.json").read_text())
    manifest = json.loads((destination / "transcript-manifest.json").read_text())

    assert receipt["transcript_status"] == "PROVEN"
    assert receipt["transcript_coverage_status"] == "PROVEN"
    assert manifest["coverage"]["exactly_once"] is True
    assert manifest["coverage"]["missing_indices"] == []
    assert "[00:00:01]" in (destination / "transcript.md").read_text()


def test_chunked_outputs_cover_every_segment_exactly_once(tmp_path):
    segments = [
        TranscriptSegment(
            text=f"Segment {index} " + (str(index) * 4_500),
            start=float(index),
            duration=1.25,
        )
        for index in range(1, 6)
    ]
    destination = write_bundle(_bundle(segments), tmp_path)

    jsonl_path = destination / "transcript.jsonl"
    records = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    manifest = json.loads((destination / "transcript-manifest.json").read_text())
    receipt = json.loads((destination / "receipt.json").read_text())

    expected = list(range(1, len(segments) + 1))
    assert [record["index"] for record in records] == expected
    assert manifest["segment_count"] == len(segments)
    assert manifest["chunk_count"] > 1
    assert manifest["coverage"]["status"] == "PROVEN"
    assert manifest["coverage"]["exactly_once"] is True
    assert manifest["coverage"]["ordered_contiguous"] is True
    assert manifest["coverage"]["missing_indices"] == []
    assert manifest["coverage"]["duplicate_indices"] == []
    assert manifest["coverage"]["unexpected_indices"] == []

    represented = []
    headings = []
    for chunk in manifest["chunks"]:
        represented.extend(
            range(chunk["first_segment"], chunk["last_segment"] + 1)
        )
        chunk_path = destination / chunk["path"]
        assert chunk["sha256"] == _sha256(chunk_path)
        headings.extend(
            int(value)
            for value in re.findall(
                r"^## Segment (\d{6})",
                chunk_path.read_text(),
                flags=re.MULTILINE,
            )
        )
        assert receipt["sha256"][chunk["path"]] == _sha256(chunk_path)

    assert represented == expected
    assert headings == expected
    assert manifest["transcript_jsonl"]["line_count"] == len(segments)
    assert manifest["transcript_jsonl"]["sha256"] == _sha256(jsonl_path)
    assert receipt["sha256"]["transcript.jsonl"] == _sha256(jsonl_path)
    assert receipt["transcript_chunk_count"] == manifest["chunk_count"]


def test_manifest_is_not_applicable_without_transcript(tmp_path):
    destination = write_bundle(_bundle(None), tmp_path)
    manifest = json.loads((destination / "transcript-manifest.json").read_text())
    receipt = json.loads((destination / "receipt.json").read_text())

    assert receipt["transcript_status"] == "NOT_PROVEN"
    assert receipt["transcript_coverage_status"] == "NOT_APPLICABLE"
    assert manifest["segment_count"] == 0
    assert manifest["chunk_count"] == 0
    assert manifest["coverage"]["status"] == "NOT_APPLICABLE"
    assert not (destination / "chunks").exists()
