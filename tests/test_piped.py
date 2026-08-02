from aitubetranscript import piped


def test_piped_returns_description_and_comments(monkeypatch):
    monkeypatch.setattr(piped, "_PIPED_INSTANCES", ("https://piped.example",))

    def fake_fetch_json(url: str, timeout: int):
        assert timeout == 8
        if "/streams/" in url:
            return {
                "title": "Example video",
                "description": "Full public description",
                "uploader": "Example channel",
                "uploaderUrl": "/channel/UC123",
                "duration": 120,
                "views": 42,
                "likes": 7,
                "thumbnailUrl": "https://example.test/thumb.jpg",
            }
        return {
            "disabled": False,
            "comments": [
                {
                    "author": "Viewer",
                    "commentText": "Useful <b>demo</b><br>Thanks",
                    "likeCount": 3,
                }
            ],
        }

    monkeypatch.setattr(piped, "_fetch_json", fake_fetch_json)
    attempts = []
    metadata, comments = piped.fetch_piped_data("x8W_S9zmodk", 20, attempts)

    assert metadata["description"] == "Full public description"
    assert metadata["channel_id"] == "UC123"
    assert comments == [
        {
            "author": "Viewer",
            "text": "Useful demo\nThanks",
            "like_count": 3,
            "timestamp": None,
            "parent": None,
        }
    ]
    assert all(item["ok"] for item in attempts)


def test_piped_records_instance_failure(monkeypatch):
    monkeypatch.setattr(piped, "_PIPED_INSTANCES", ("https://piped.example",))

    def fail_fetch_json(url: str, timeout: int):
        raise TimeoutError(f"timed out: {url}")

    monkeypatch.setattr(piped, "_fetch_json", fail_fetch_json)
    attempts = []
    metadata, comments = piped.fetch_piped_data("x8W_S9zmodk", 5, attempts)

    assert metadata == {}
    assert comments == []
    assert len(attempts) == 2
    assert not any(item["ok"] for item in attempts)
