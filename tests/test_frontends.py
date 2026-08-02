import pytest

from aitubetranscript.frontends import (
    FrontendError,
    _eligible_invidious_instances,
    parse_transcript_markdown,
)


def test_parse_timestamped_transcript_markdown():
    body = """# Transcript: Example
Language: en
Duration: 1:00

[0:01] First sentence.
[0:04] Second sentence.
"""
    transcript = parse_transcript_markdown(body, "proxy", "en")
    assert [segment.text for segment in transcript.segments] == [
        "First sentence.",
        "Second sentence.",
    ]
    assert transcript.segments[0].start == 1.0
    assert transcript.segments[0].duration == 3.0


def test_parse_untimed_transcript_fallback():
    body = "# Transcript\n\nThis is a long enough untimed transcript body."
    transcript = parse_transcript_markdown(body, "proxy", "en")
    assert len(transcript.segments) == 1
    assert "untimed transcript" in transcript.segments[0].text


def test_rejects_html_response():
    with pytest.raises(FrontendError):
        parse_transcript_markdown("<!doctype html><html></html>", "proxy", "en")


def test_filters_invidious_registry_for_public_https_api_instances():
    registry = [
        [
            "good.example",
            {
                "api": True,
                "type": "https",
                "uri": "https://good.example",
                "monitor": {"down": False},
            },
        ],
        [
            "down.example",
            {
                "api": True,
                "type": "https",
                "uri": "https://down.example",
                "monitor": {"down": True},
            },
        ],
        [
            "private",
            {
                "api": True,
                "type": "https",
                "uri": "https://127.0.0.1",
                "monitor": {"down": False},
            },
        ],
    ]
    assert _eligible_invidious_instances(registry) == ["https://good.example"]
