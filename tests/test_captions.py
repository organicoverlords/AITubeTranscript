from aitubetranscript.captions import parse_json3, parse_vtt, select_caption_track


def test_parse_json3():
    payload = (
        b'{"events":[{"tStartMs":1000,"dDurationMs":2000,'
        b'"segs":[{"utf8":"Hello "},{"utf8":"world"}]}]}'
    )
    transcript = parse_json3(payload, "test", "en")
    assert transcript.segments[0].text == "Hello world"
    assert transcript.segments[0].start == 1.0
    assert transcript.segments[0].duration == 2.0


def test_parse_vtt_deduplicates_rolling_captions():
    payload = (
        b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n\n"
        b"00:00:02.000 --> 00:00:03.000\nHello\n"
    )
    transcript = parse_vtt(payload, "test", "en")
    assert [item.text for item in transcript.segments] == ["Hello"]


def test_select_manual_before_automatic():
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "manual"}]},
        "automatic_captions": {"en": [{"ext": "json3", "url": "auto"}]},
    }
    language, track, generated = select_caption_track(info, ["en"])
    assert language == "en"
    assert track["url"] == "manual"
    assert generated is False
