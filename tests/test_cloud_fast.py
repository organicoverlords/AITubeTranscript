import os
import subprocess
import sys
import threading
from pathlib import Path

from aitubetranscript import cloud_fast
from aitubetranscript.models import TranscriptData, TranscriptSegment


def test_cloud_modules_import_without_site_packages():
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "import aitubetranscript.cli; "
                "import aitubetranscript.cloud_fast; "
                "print('CLOUD_FAST_IMPORT=PROVEN')"
            ),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CLOUD_FAST_IMPORT=PROVEN" in result.stdout


def test_fetch_youtube_cloud_builds_complete_bundle(monkeypatch):
    transcript = TranscriptData(
        source="edge:test",
        language="English",
        language_code="en",
        is_generated=False,
        segments=[TranscriptSegment(text="Complete text", start=0.0, duration=1.0)],
    )

    monkeypatch.setattr(
        cloud_fast,
        "fetch_transcript_proxy",
        lambda video_id, languages, attempts: transcript,
    )
    monkeypatch.setattr(
        cloud_fast,
        "fetch_youtube_data_api",
        lambda video_id, key, limit, attempts: (
            {
                "id": video_id,
                "title": "Title",
                "description": "Description",
                "channel": "Channel",
                "comment_count": 2,
            },
            [
                {
                    "author": "A",
                    "text": "First",
                    "like_count": 2,
                    "timestamp": None,
                    "parent": None,
                },
                {
                    "author": "B",
                    "text": "Second",
                    "like_count": 1,
                    "timestamp": None,
                    "parent": None,
                },
            ],
        ),
    )

    bundle = cloud_fast.fetch_youtube_cloud(
        "x8W_S9zmodk",
        youtube_api_key="test-key",
        comment_limit=2,
    )

    assert bundle.video_id == "x8W_S9zmodk"
    assert bundle.transcript is transcript
    assert bundle.metadata["description"] == "Description"
    assert [comment.text for comment in bundle.comments] == ["First", "Second"]
    assert bundle.attempts[0] == {"source": "fast cloud path", "ok": True}


def test_cloud_transcript_and_api_fetches_run_concurrently(monkeypatch):
    barrier = threading.Barrier(2, timeout=2.0)
    transcript = TranscriptData(
        source="edge:test",
        language="English",
        language_code="en",
        is_generated=False,
        segments=[TranscriptSegment(text="Text", start=0.0, duration=1.0)],
    )

    def fetch_transcript(video_id, languages, attempts):
        barrier.wait()
        return transcript

    def fetch_api(video_id, key, limit, attempts):
        barrier.wait()
        return {
            "id": video_id,
            "title": "Title",
            "description": "Description",
        }, []

    monkeypatch.setattr(cloud_fast, "fetch_transcript_proxy", fetch_transcript)
    monkeypatch.setattr(cloud_fast, "fetch_youtube_data_api", fetch_api)

    bundle = cloud_fast.fetch_youtube_cloud(
        "x8W_S9zmodk",
        youtube_api_key="test-key",
        include_comments=False,
    )

    assert bundle.transcript is transcript
    assert bundle.metadata["description"] == "Description"
