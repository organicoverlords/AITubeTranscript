from aitubetranscript.cleaning import (
    clean_rolling_texts,
    collapse_adjacent_repeats,
    remove_leading_overlap,
)
from aitubetranscript.models import TranscriptData, TranscriptSegment


def test_collapses_repeated_caption_blocks():
    text = (
        "Nvidia just released its brand new Nvidia just released its brand new "
        "real-time AI animation tool and real-time AI animation tool and "
        "real-time AI animation tool and it runs locally"
    )
    assert collapse_adjacent_repeats(text) == (
        "Nvidia just released its brand new real-time AI animation tool and "
        "it runs locally"
    )


def test_removes_cross_segment_overlap():
    previous = "I will show you how to set it up on your own PC"
    current = "how to set it up on your own PC and how to export animation"
    assert remove_leading_overlap(previous, current) == "and how to export animation"


def test_clean_rolling_texts_preserves_segment_count():
    cleaned = clean_rolling_texts(
        [
            "A person walks forward A person walks forward and turns left",
            "and turns left before stopping",
        ]
    )
    assert cleaned == [
        "A person walks forward and turns left",
        "before stopping",
    ]


def test_transcript_data_cleans_segments_automatically():
    transcript = TranscriptData(
        source="test",
        language="English",
        language_code="en",
        is_generated=True,
        segments=[
            TranscriptSegment(
                text="hello from the video hello from the video next sentence",
                start=0,
                duration=2,
            )
        ],
    )
    assert transcript.segments[0].text == "hello from the video next sentence"
