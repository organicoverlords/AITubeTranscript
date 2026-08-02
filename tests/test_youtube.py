import pytest

from aitubetranscript.youtube import InvalidYouTubeURL, extract_video_id


@pytest.mark.parametrize(
    "value",
    [
        "x8W_S9zmodk",
        "https://www.youtube.com/watch?v=x8W_S9zmodk",
        "https://youtu.be/x8W_S9zmodk?t=5",
        "https://www.youtube.com/shorts/x8W_S9zmodk",
        "https://www.youtube.com/live/x8W_S9zmodk",
    ],
)
def test_extract_video_id(value):
    assert extract_video_id(value) == "x8W_S9zmodk"


def test_rejects_non_youtube_url():
    with pytest.raises(InvalidYouTubeURL):
        extract_video_id("https://example.com/watch?v=x8W_S9zmodk")
