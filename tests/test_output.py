import json

from aitubetranscript.models import ResearchBundle, TranscriptData, TranscriptSegment
from aitubetranscript.output import write_bundle


def test_write_bundle(tmp_path):
    bundle = ResearchBundle(
        schema_version="1.0",
        fetched_at="2026-08-02T00:00:00+00:00",
        video_id="x8W_S9zmodk",
        canonical_url="https://www.youtube.com/watch?v=x8W_S9zmodk",
        metadata={"title": "Test", "description": "Desc"},
        transcript=TranscriptData(
            source="test",
            language="English",
            language_code="en",
            is_generated=False,
            segments=[TranscriptSegment(text="Hello", start=1.0, duration=2.0)],
        ),
        comments=[],
        warnings=[],
        attempts=[],
    )
    destination = write_bundle(bundle, tmp_path)
    receipt = json.loads((destination / "receipt.json").read_text())
    assert receipt["transcript_status"] == "PROVEN"
    assert "[00:00:01]" in (destination / "transcript.md").read_text()
