from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from .captions import fetch_caption_document, parse_json3, parse_vtt, select_caption_track
from .frontends import fetch_invidious_data, fetch_oembed, fetch_transcript_proxy
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
    _enrich_metadata(video_id, url, info, options, attempts)

    transcript = _fetch_transcript_api(video_id, options, attempts)
    if transcript is None:
        transcript = _fetch_from_yt_dlp_tracks(info, options, attempts)
    if transcript is None:
        transcript = fetch_transcript_proxy(video_id, options.languages, attempts)
        if transcript is not None:
            warnings.append(
                "Transcript was retrieved through a third-party public edge service; "
                "verify important quotations against the video."
            )
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


def _enrich_metadata(
    video_id: str,
    url: str,
    info: dict[str, Any],
    options: FetchOptions,
    attempts: list[dict[str, Any]],
) -> None:
    if not info.get("title"):
        _merge_missing(info, fetch_oembed(url, attempts))

    needs_frontend = (
        not info.get("title")
        or not info.get("description")
        or (options.include_comments and not info.get("comments"))
    )
    if not needs_frontend:
        return

    metadata, comments = fetch_invidious_data(
        video_id,
        options.comment_limit if options.include_comments else 0,
        attempts,
    )
    _merge_missing(info, metadata)
    if options.include_comments and comments and not info.get("comments"):
        info["comments"] = comments


def _merge_missing(target: dict[str, Any], fallback: dict[str, Any]) -> None:
    for key, value in fallback.items():
        if value is not None and not target.get(key):
            target[key] = value


def _fetch_metadata(
    url: str,
    options: FetchOptions,
    attempts: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    profiles: tuple[tuple[str, dict[str, list[str]]], ...] = (
        ("yt-dlp default clients", {}),
        (
            "yt-dlp non-web clients",
            {"player_client": ["default", "-web"], "skip": ["translated_subs"]},
        ),
        (
            "yt-dlp tv/ios clients",
            {
                "player_client": ["tv", "ios"],
                "player_skip": ["webpage"],
                "skip": ["translated_subs"],
            },
        ),
    )
    info: dict[str, Any] = {}
    for profile_name, extractor_overrides in profiles:
        params = _base_yt_dlp_params(options)
        params["extractor_args"] = {"youtube": extractor_overrides}
        try:
            with YoutubeDL(params) as downloader:
                extracted = downloader.extract_info(url, download=False)
            if extracted:
                info = extracted
                attempts.append({"source": profile_name, "ok": True})
                break
            attempts.append(
                {"source": profile_name, "ok": False, "error": "empty result"}
            )
        except Exception as exc:
            attempts.append({"source": profile_name, "ok": False, "error": str(exc)})

    if not info:
        warnings.append(
            "Core YouTube metadata extraction failed for every yt-dlp client profile."
        )
        info = {"id": extract_video_id(url), "webpage_url": url}

    if options.include_comments:
        comments = _fetch_comments(url, options, attempts)
        if comments:
            info["comments"] = comments
    return info


def _fetch_comments(
    url: str,
    options: FetchOptions,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    params = _base_yt_dlp_params(options)
    params.update(
        {
            "getcomments": True,
            "extractor_args": {
                "youtube": {
                    "comment_sort": ["top"],
                    "max_comments": [
                        f"{max(0, options.comment_limit)},all,all,all,1"
                    ],
                }
            },
        }
    )
    try:
        with YoutubeDL(params) as downloader:
            extracted = downloader.extract_info(url, download=False) or {}
        comments = extracted.get("comments") or []
        attempts.append(
            {
                "source": "yt-dlp comments",
                "ok": bool(comments),
                "count": len(comments),
            }
        )
        return comments
    except Exception as exc:
        attempts.append({"source": "yt-dlp comments", "ok": False, "error": str(exc)})
        return []


def _base_yt_dlp_params(options: FetchOptions) -> dict[str, Any]:
    params: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "getcomments": False,
    }
    if options.cookies:
        params["cookiefile"] = str(options.cookies)
    if options.proxy:
        params["proxy"] = options.proxy
    return params


def _fetch_transcript_api(
    video_id: str,
    options: FetchOptions,
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    try:
        fetched = YouTubeTranscriptApi().fetch(
            video_id,
            languages=list(options.languages),
        )
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
        attempts.append(
            {"source": "youtube-transcript-api", "ok": bool(transcript.segments)}
        )
        return transcript if transcript.segments else None
    except Exception as exc:
        attempts.append(
            {"source": "youtube-transcript-api", "ok": False, "error": str(exc)}
        )
        return None


def _fetch_from_yt_dlp_tracks(
    info: dict[str, Any],
    options: FetchOptions,
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    selected = select_caption_track(info, list(options.languages))
    if selected is None:
        attempts.append(
            {"source": "yt-dlp caption track", "ok": False, "error": "no track"}
        )
        return None
    language_code, track, generated = selected
    url = track.get("url")
    extension = track.get("ext")
    if not url:
        attempts.append(
            {
                "source": "yt-dlp caption track",
                "ok": False,
                "error": "track has no URL",
            }
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
        attempts.append(
            {"source": "yt-dlp caption track", "ok": False, "error": str(exc)}
        )
        return None


def _fetch_with_whisper(
    url: str,
    options: FetchOptions,
    attempts: list[dict[str, Any]],
) -> TranscriptData | None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        attempts.append(
            {
                "source": "faster-whisper",
                "ok": False,
                "error": (
                    "optional dependency missing; install "
                    "aitube-transcript[whisper]"
                ),
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
            segments_iter, details = model.transcribe(
                str(audio_path),
                vad_filter=True,
            )
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
        "published",
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
