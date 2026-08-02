from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from .captions import fetch_caption_document, parse_json3, parse_vtt, select_caption_track
from .models import CommentData, ResearchBundle, TranscriptData, TranscriptSegment
from .youtube import canonical_url, extract_video_id


@dataclass(slots=True)
class FetchOptions:
    languages: tuple[str, ...] = ("en",)
    comment_limit: int = 100
    include_comments: bool = True
    cookies: Path | None = None
    proxy: str | None = None
    whisper: bool = False
    whisper_model: str = "tiny"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"


def fetch_youtube(value: str, options: FetchOptions | None = None) -> ResearchBundle:
    options = options or FetchOptions()
    video_id = extract_video_id(value)
    url = canonical_url(video_id)
    warnings: list[str] = []
    attempts: list[dict[str, Any]] = []

    info = _fetch_metadata(url, options, attempts, warnings)
    transcript = _fetch_transcript_api(video_id, options, attempts)
    if transcript is None:
        transcript = _fetch_from_yt_dlp_tracks(info, options, attempts)
    if transcript is None and options.whisper:
        transcript = _fetch_with_whisper(url, options, attempts)
    if transcript is None:
        warnings.append(
            "No transcript was retrieved. Enable --whisper for audio transcription fallback."
        )

    comments = _normalize_comments(info.get("comments") or [], options.comment_limit)
    if options.include_comments and not comments:
        warnings.append(
            "No comments were returned; YouTube may have disabled or blocked comment extraction."
        )

    return ResearchBundle(
        schema_version="1.0",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        video_id=video_id,
        canonical_url=url,
        metadata=_clean_metadata(info),
        transcript=transcript,
        comments=comments,
        warnings=warnings,
        attempts=attempts,
    )


def _fetch_metadata(
    url: str,
    options: FetchOptions,
    attempts: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "getcomments": options.include_comments,
        "extractor_args": {
            "youtube": {
                "comment_sort": ["top"],
                "max_comments": [f"{max(0, options.comment_limit)},all,all,all,1"],
            }
        },
    }
    if options.cookies:
        params["cookiefile"] = str(options.cookies)
    if options.proxy:
        params["proxy"] = options.proxy

    try:
        with YoutubeDL(params) as downloader:
            info = downloader.extract_info(url, download=False)
        attempts.append({"source": "yt-dlp metadata/comments", "ok": True})
        return info or {}
    except Exception as exc:  # yt-dlp raises a large family of extractor errors
        attempts.append({"source": "yt-dlp metadata/comments", "ok": False, "error": str(exc)})
        warnings.append(f"Metadata extraction failed: {exc}")
        return {"id": extract_video_id(url), "webpage_url": url}


def _fetch_transcript_api(
    video_id: str, options: FetchOptions, attempts: list[dict[str, Any]]
) -> TranscriptData | None:
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(options.languages))
        raw = fetched.to_raw_data()
        transcript = TranscriptData(
            source="youtube-transcript-api",
            language=getattr(fetched, "language", None),
            language_code=getattr(fetched, "language_code", None),
            is_generated=getattr(fetched, "is_generated", None),
            segments=[
                TranscriptSegment(
                    text=str(item.get("text", "")).strip(),
                    start=float(item.get("start", 0)),
                    duration=float(item.get("duration", 0)),
                )
                for item in raw
                if str(item.get("text", "")).strip()
            ],
        )
        attempts.append({"source": "youtube-transcript-api", "ok": bool(transcript.segments)})
        return transcript if transcript.segments else None
    except Exception as exc:
        attempts.append({"source": "youtube-transcript-api", "ok": False, "error": str(exc)})
        return None


def _fetch_from_yt_dlp_tracks(
    info: dict[str, Any], options: FetchOptions, attempts: list[dict[str, Any]]
) -> TranscriptData | None:
    selected = select_caption_track(info, list(options.languages))
    if selected is None:
        attempts.append({"source": "yt-dlp caption track", "ok": False, "error": "no track"})
        return None
    language_code, track, generated = selected
    url = track.get("url")
    extension = track.get("ext")
    if not url:
        attempts.append(
            {"source": "yt-dlp caption track", "ok": False, "error": "track has no URL"}
        )
        return None
    try:
        payload = fetch_caption_document(url)
        source = f"yt-dlp {'automatic' if generated else 'manual'} captions"
        transcript = (
            parse_json3(payload, source, language_code)
            if extension == "json3"
            else parse_vtt(payload, source, language_code)
        )
        attempts.append({"source": source, "ok": bool(transcript.segments)})
        return transcript if transcript.segments else None
    except Exception as exc:
        attempts.append({"source": "yt-dlp caption track", "ok": False, "error": str(exc)})
        return None


def _fetch_with_whisper(
    url: str, options: FetchOptions, attempts: list[dict[str, Any]]
) -> TranscriptData | None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        attempts.append(
            {
                "source": "faster-whisper",
                "ok": False,
                "error": "optional dependency missing; install aitube-transcript[whisper]",
            }
        )
        return None

    try:
        with tempfile.TemporaryDirectory(prefix="aitube-") as temp_dir:
            output = str(Path(temp_dir) / "audio.%(ext)s")
            params: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
                "outtmpl": output,
                "noplaylist": True,
            }
            if options.cookies:
                params["cookiefile"] = str(options.cookies)
            if options.proxy:
                params["proxy"] = options.proxy
            with YoutubeDL(params) as downloader:
                downloaded = downloader.extract_info(url, download=True)
                audio_path = Path(downloader.prepare_filename(downloaded))

            model = WhisperModel(
                options.whisper_model,
                device=options.whisper_device,
                compute_type=options.whisper_compute_type,
            )
            segments_iter, details = model.transcribe(str(audio_path), vad_filter=True)
            segments = [
                TranscriptSegment(
                    text=segment.text.strip(),
                    start=float(segment.start),
                    duration=max(0.0, float(segment.end) - float(segment.start)),
                )
                for segment in segments_iter
                if segment.text.strip()
            ]
            transcript = TranscriptData(
                source=f"faster-whisper:{options.whisper_model}",
                language=getattr(details, "language", None),
                language_code=getattr(details, "language", None),
                is_generated=True,
                segments=segments,
            )
            attempts.append({"source": "faster-whisper", "ok": bool(segments)})
            return transcript if segments else None
    except Exception as exc:
        attempts.append({"source": "faster-whisper", "ok": False, "error": str(exc)})
        return None


def _normalize_comments(raw: list[dict[str, Any]], limit: int) -> list[CommentData]:
    comments: list[CommentData] = []
    for item in raw[: max(0, limit)]:
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        comments.append(
            CommentData(
                author=item.get("author"),
                text=text,
                like_count=_as_int(item.get("like_count")),
                timestamp=_as_int(item.get("timestamp")),
                parent=item.get("parent"),
            )
        )
    return comments


def _clean_metadata(info: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "title",
        "description",
        "channel",
        "channel_id",
        "channel_url",
        "uploader",
        "upload_date",
        "timestamp",
        "duration",
        "duration_string",
        "view_count",
        "like_count",
        "comment_count",
        "availability",
        "age_limit",
        "categories",
        "tags",
        "thumbnail",
        "webpage_url",
    )
    return {key: info.get(key) for key in keys if info.get(key) is not None}


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
