import pytest

from aitubetranscript.request import resolve_request


def test_owner_issue_request():
    event = {
        "issue": {
            "title": "[fetch] https://youtu.be/x8W_S9zmodk",
            "body": "",
            "author_association": "OWNER",
        }
    }
    result = resolve_request(event)
    assert result["video_id"] == "x8W_S9zmodk"


def test_public_issue_is_denied_by_default():
    event = {
        "issue": {
            "title": "[fetch] https://youtu.be/x8W_S9zmodk",
            "body": "",
            "author_association": "NONE",
        }
    }
    with pytest.raises(PermissionError):
        resolve_request(event)


def test_workflow_dispatch_request():
    event = {"inputs": {"video_url": "x8W_S9zmodk", "languages": "en,fi"}}
    result = resolve_request(event)
    assert result["languages"] == "en,fi"
