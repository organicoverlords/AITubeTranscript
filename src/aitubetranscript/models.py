from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(slots=True)
class TranscriptData:
    source: str
    language: str | None
    language_code: str | None
    is_generated: bool | None
    segments: list[TranscriptSegment] = field(default_factory=list)


@dataclass(slots=True)
class CommentData:
    author: str | None
    text: str
    like_count: int | None = None
    timestamp: int | None = None
    parent: str | None = None


@dataclass(slots=True)
class ResearchBundle:
    schema_version: str
    fetched_at: str
    video_id: str
    canonical_url: str
    metadata: dict[str, Any]
    transcript: TranscriptData | None
    comments: list[CommentData]
    warnings: list[str]
    attempts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
