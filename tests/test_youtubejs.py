from aitubetranscript.models import ResearchBundle
from aitubetranscript.youtubejs import enrich_bundle_with_youtubejs


def test_youtubejs_enrichment_fills_missing_description_and_comments(monkeypatch):
    bundle = ResearchBundle(
        schema_version="1.1",
        fetched_at="2026-08-02T00:00:00+00:00",
        video_id="x8W_S9zmodk",
        canonical_url="https://www.youtube.com/watch?v=x8W_S9zmodk",
        metadata={"title": "Existing title"},
        transcript=None,
        comments=[],
        warnings=["No comments were returned. Configure another route."],
        attempts=[],
    )

    def fake_fetch(video_id, comment_limit, attempts):
        assert video_id == "x8W_S9zmodk"
        assert comment_limit == 2
        attempts.append({"source": "fake", "ok": True})
        return (
            {
                "title": "Replacement title",
                "description": "Full description",
                "channel": "Channel",
            },
            [
                {"author": "One", "text": "First", "like_count": 4},
                {"author": "Two", "text": "Second", "like_count": None},
                {"author": "Three", "text": "Third", "like_count": 1},
            ],
        )

    monkeypatch.setattr(
        "aitubetranscript.youtubejs.fetch_youtubejs_data",
        fake_fetch,
    )
    enrich_bundle_with_youtubejs(bundle, 2)

    assert bundle.metadata["title"] == "Existing title"
    assert bundle.metadata["description"] == "Full description"
    assert [comment.text for comment in bundle.comments] == ["First", "Second"]
    assert not any(item.startswith("No comments were returned") for item in bundle.warnings)
    assert bundle.attempts == [{"source": "fake", "ok": True}]


def test_youtubejs_enrichment_skips_complete_bundle(monkeypatch):
    bundle = ResearchBundle(
        schema_version="1.1",
        fetched_at="2026-08-02T00:00:00+00:00",
        video_id="x8W_S9zmodk",
        canonical_url="https://www.youtube.com/watch?v=x8W_S9zmodk",
        metadata={"description": "Already present"},
        transcript=None,
        comments=[],
        warnings=[],
        attempts=[],
    )

    def should_not_run(*args, **kwargs):
        raise AssertionError("YouTube.js should not run")

    monkeypatch.setattr(
        "aitubetranscript.youtubejs.fetch_youtubejs_data",
        should_not_run,
    )
    enrich_bundle_with_youtubejs(bundle, 0)

    assert bundle.metadata["description"] == "Already present"
    assert bundle.attempts == []
