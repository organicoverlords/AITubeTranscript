from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from .output import write_bundle
from .youtube import canonical_url, extract_video_id

_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,100}$")
_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_USER_AGENT = "AITubeTranscript/0.3 (+https://github.com/organicoverlords/AITubeTranscript)"
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_VIDEOS = 100
MAX_BATCH_VIDEOS = 500
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 6


class InvalidBatchRequest(ValueError):
    pass


def extract_playlist_id(value: str) -> str:
    candidate = value.strip()
    if _PLAYLIST_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise InvalidBatchRequest("Only youtube.com and youtu.be playlist URLs are accepted")

    playlist_id = (parse_qs(parsed.query).get("list") or [None])[0]
    if not playlist_id or not _PLAYLIST_ID_RE.fullmatch(playlist_id):
        raise InvalidBatchRequest("Could not extract a valid YouTube playlist ID")
    return playlist_id


def normalize_batch_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise InvalidBatchRequest("Batch request must be a JSON object")

    request_id = str(request.get("request_id") or _default_batch_id()).strip()
    if not _BATCH_ID_RE.fullmatch(request_id):
        raise InvalidBatchRequest(
            "request_id must be 1-100 characters using letters, numbers, dot, dash, or underscore"
        )

    video_urls = _combined_values(request, "video_url", "video_urls")
    playlist_urls = _combined_values(request, "playlist_url", "playlist_urls")
    if not video_urls and not playlist_urls:
        raise InvalidBatchRequest(
            "Provide video_url, video_urls, playlist_url, or playlist_urls"
        )

    languages = str(request.get("languages", "en")).strip() or "en"
    if any(character in languages for character in "\r\n"):
        raise InvalidBatchRequest("languages must be a single line")

    comments = _bounded_int(request.get("comments", 100), "comments", 0, 1000)
    max_videos = _bounded_int(
        request.get("max_videos", DEFAULT_MAX_VIDEOS),
        "max_videos",
        1,
        MAX_BATCH_VIDEOS,
    )
    start_index = _bounded_int(
        request.get("playlist_start_index", 0),
        "playlist_start_index",
        0,
        1_000_000,
    )
    concurrency = _bounded_int(
        request.get("concurrency", DEFAULT_CONCURRENCY),
        "concurrency",
        1,
        MAX_CONCURRENCY,
    )
    whisper = _as_bool(request.get("whisper", False), "whisper")

    return {
        "request_id": request_id,
        "video_urls": video_urls,
        "playlist_urls": playlist_urls,
        "languages": languages,
        "comments": comments,
        "whisper": whisper,
        "max_videos": max_videos,
        "playlist_start_index": start_index,
        "concurrency": 1 if whisper else concurrency,
    }


def fetch_playlist_video_ids(
    value: str,
    api_key: str | None,
    *,
    start_index: int = 0,
    limit: int = DEFAULT_MAX_VIDEOS,
) -> tuple[list[str], dict[str, Any]]:
    playlist_id = extract_playlist_id(value)
    if not api_key:
        raise InvalidBatchRequest(
            "YOUTUBE_API_KEY is required to expand playlist URLs in the cloud workflow"
        )
    if limit < 1:
        raise InvalidBatchRequest("Playlist limit must be positive")

    selected: list[str] = []
    skipped = 0
    page_token: str | None = None
    exhausted = False
    api_pages = 0
    catalog_items_seen = 0

    while len(selected) < limit:
        parameters = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            parameters["pageToken"] = page_token

        payload = _fetch_json(
            "https://www.googleapis.com/youtube/v3/playlistItems?"
            + urlencode(parameters),
            timeout=25,
        )
        api_pages += 1
        items = payload.get("items") or []
        for item in items:
            video_id = str(
                (item.get("contentDetails") or {}).get("videoId") or ""
            ).strip()
            if not video_id:
                continue
            catalog_items_seen += 1
            if skipped < start_index:
                skipped += 1
                continue
            selected.append(video_id)
            if len(selected) >= limit:
                break

        next_page = str(payload.get("nextPageToken") or "").strip()
        if not next_page:
            exhausted = True
            page_token = None
            break
        page_token = next_page

    return selected, {
        "playlist_id": playlist_id,
        "playlist_url": value,
        "start_index": start_index,
        "selected_count": len(selected),
        "catalog_items_seen": catalog_items_seen,
        "api_pages": api_pages,
        "catalog_exhausted": exhausted,
        "truncated_by_limit": not exhausted and len(selected) >= limit,
        "next_page_token_present": bool(page_token),
    }


def resolve_batch_video_ids(
    request: dict[str, Any],
    youtube_api_key: str | None,
) -> tuple[list[str], list[dict[str, Any]], int]:
    direct_ids = [extract_video_id(value) for value in request["video_urls"]]
    if len(direct_ids) > request["max_videos"]:
        raise InvalidBatchRequest(
            f"Direct video list exceeds max_videos={request['max_videos']}"
        )

    combined = list(direct_ids)
    playlists: list[dict[str, Any]] = []
    for playlist_url in request["playlist_urls"]:
        remaining = request["max_videos"] - len(_dedupe(combined))
        if remaining <= 0:
            playlists.append(
                {
                    "playlist_id": extract_playlist_id(playlist_url),
                    "playlist_url": playlist_url,
                    "start_index": request["playlist_start_index"],
                    "selected_count": 0,
                    "catalog_items_seen": 0,
                    "api_pages": 0,
                    "catalog_exhausted": False,
                    "truncated_by_limit": True,
                    "next_page_token_present": False,
                    "not_expanded_reason": "max_videos reached before this playlist",
                }
            )
            continue
        playlist_ids, metadata = fetch_playlist_video_ids(
            playlist_url,
            youtube_api_key,
            start_index=request["playlist_start_index"],
            limit=remaining,
        )
        combined.extend(playlist_ids)
        playlists.append(metadata)

    deduped = _dedupe(combined)
    duplicate_count = len(combined) - len(deduped)
    if not deduped:
        raise InvalidBatchRequest("The request resolved to zero videos")
    return deduped[: request["max_videos"]], playlists, duplicate_count


def run_batch(
    raw_request: dict[str, Any],
    output_root: Path,
    *,
    youtube_api_key: str | None = None,
    fast_cloud: bool = False,
) -> tuple[dict[str, Any], Path]:
    request = normalize_batch_request(raw_request)
    if fast_cloud and request["whisper"]:
        raise InvalidBatchRequest(
            "Whisper cannot run through --fast-cloud; use the standard batch path"
        )

    started_at = datetime.now(timezone.utc)
    video_ids, playlists, duplicate_count = resolve_batch_video_ids(
        request,
        youtube_api_key,
    )
    results: list[dict[str, Any] | None] = [None] * len(video_ids)

    with ThreadPoolExecutor(
        max_workers=request["concurrency"],
        thread_name_prefix="aitube-batch",
    ) as executor:
        future_map = {
            executor.submit(
                _fetch_one,
                video_id,
                request,
                output_root,
                youtube_api_key,
                fast_cloud,
            ): index
            for index, video_id in enumerate(video_ids)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            try:
                result = future.result()
                result["index"] = index + 1
                results[index] = result
            except Exception as exc:
                video_id = video_ids[index]
                results[index] = {
                    "index": index + 1,
                    "video_id": video_id,
                    "canonical_url": canonical_url(video_id),
                    "status": "FAILED",
                    "error": str(exc),
                    "private_result_path": f"videos/{video_id}/latest/",
                }

    finalized_results = [result for result in results if result is not None]
    proven_count = sum(result["status"] == "PROVEN" for result in finalized_results)
    partial_count = sum(result["status"] == "PARTIAL" for result in finalized_results)
    failed_count = sum(result["status"] == "FAILED" for result in finalized_results)
    playlist_truncated = any(item["truncated_by_limit"] for item in playlists)

    if proven_count == len(video_ids) and not playlist_truncated:
        batch_status = "PROVEN"
    elif proven_count or partial_count:
        batch_status = "PARTIAL"
    else:
        batch_status = "FAILED"

    completed_at = datetime.now(timezone.utc)
    batch_directory = output_root / "batches" / request["request_id"]
    batch_directory.mkdir(parents=True, exist_ok=True)
    expected_indices = list(range(1, len(video_ids) + 1))
    actual_indices = [int(result["index"]) for result in finalized_results]
    duplicate_indices = sorted(
        index for index in set(actual_indices) if actual_indices.count(index) > 1
    )
    missing_indices = sorted(set(expected_indices) - set(actual_indices))
    unexpected_indices = sorted(set(actual_indices) - set(expected_indices))

    request_for_receipt = {
        key: value
        for key, value in request.items()
        if key not in {"video_urls", "playlist_urls"}
    }
    request_for_receipt["video_urls"] = request["video_urls"]
    request_for_receipt["playlist_urls"] = request["playlist_urls"]
    request_json = json.dumps(
        request_for_receipt,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    receipt = {
        "schema_version": "1.0",
        "batch_id": request["request_id"],
        "status": batch_status,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
        "request": request_for_receipt,
        "request_sha256": hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
        "resolved_video_count": len(video_ids),
        "resolved_video_ids": video_ids,
        "duplicate_video_count_removed": duplicate_count,
        "playlist_expansions": playlists,
        "playlist_catalog_status": "PARTIAL" if playlist_truncated else "PROVEN",
        "proven_count": proven_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "coverage": {
            "status": (
                "PROVEN"
                if not missing_indices and not duplicate_indices and not unexpected_indices
                else "REJECTED"
            ),
            "exactly_once": (
                not missing_indices and not duplicate_indices and not unexpected_indices
            ),
            "missing_indices": missing_indices,
            "duplicate_indices": duplicate_indices,
            "unexpected_indices": unexpected_indices,
            "ordered_contiguous": actual_indices == expected_indices,
        },
        "results": finalized_results,
    }
    reader_manifest = {
        "schema_version": "1.0",
        "batch_id": request["request_id"],
        "status": batch_status,
        "batch_receipt": "batch-receipt.json",
        "private_batch_path": f"batches/{request['request_id']}/latest/",
        "private_read_order": [
            f"batches/{request['request_id']}/latest/batch-receipt.json",
            *[
                f"videos/{result['video_id']}/latest/reader-manifest.json"
                for result in finalized_results
                if result["status"] != "FAILED"
            ],
        ],
        "local_read_order": [
            "batch-receipt.json",
            *[
                f"../../{result['video_id']}/reader-manifest.json"
                for result in finalized_results
                if result["status"] != "FAILED"
            ],
        ],
    }

    (batch_directory / "batch-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (batch_directory / "batch-reader-manifest.json").write_text(
        json.dumps(reader_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt, batch_directory


def _fetch_one(
    video_id: str,
    request: dict[str, Any],
    output_root: Path,
    youtube_api_key: str | None,
    fast_cloud: bool,
) -> dict[str, Any]:
    languages = tuple(
        item.strip() for item in request["languages"].split(",") if item.strip()
    ) or ("en",)

    if fast_cloud:
        from .cloud_fast import fetch_youtube_cloud

        bundle = fetch_youtube_cloud(
            video_id,
            languages=languages,
            comment_limit=request["comments"],
            include_comments=request["comments"] > 0,
            youtube_api_key=youtube_api_key,
        )
    else:
        from .fetcher import FetchOptions, fetch_youtube
        from .youtubejs import enrich_bundle_with_youtubejs

        options = FetchOptions(
            languages=languages,
            comment_limit=request["comments"],
            include_comments=request["comments"] > 0,
            whisper=request["whisper"],
            youtube_api_key=youtube_api_key,
        )
        bundle = fetch_youtube(video_id, options)
        enrich_bundle_with_youtubejs(
            bundle,
            options.comment_limit if options.include_comments else 0,
        )

    destination = write_bundle(bundle, output_root)
    receipt = json.loads((destination / "receipt.json").read_text(encoding="utf-8"))
    transcript_ok = (
        receipt.get("transcript_status") == "PROVEN"
        and receipt.get("transcript_coverage_status") == "PROVEN"
    )
    comments_required = request["comments"] > 0
    comments_ok = not comments_required or (
        receipt.get("comments_status") == "PROVEN"
        and receipt.get("comments_coverage_status") == "PROVEN"
    )
    status = "PROVEN" if transcript_ok and comments_ok else "PARTIAL"

    return {
        "index": 0,
        "video_id": video_id,
        "canonical_url": canonical_url(video_id),
        "status": status,
        "transcript_status": receipt.get("transcript_status"),
        "transcript_coverage_status": receipt.get("transcript_coverage_status"),
        "comments_status": receipt.get("comments_status"),
        "comments_coverage_status": receipt.get("comments_coverage_status"),
        "segment_count": receipt.get("segment_count", 0),
        "comment_count": receipt.get("comment_count", 0),
        "fetched_at": receipt.get("fetched_at"),
        "private_result_path": f"videos/{video_id}/latest/",
    }


def _combined_values(
    request: dict[str, Any],
    singular_key: str,
    plural_key: str,
) -> list[str]:
    values: list[str] = []
    singular = request.get(singular_key)
    if singular is not None:
        values.extend(_string_values(singular, singular_key))
    plural = request.get(plural_key)
    if plural is not None:
        values.extend(_string_values(plural, plural_key))
    return _dedupe(value.strip() for value in values if value.strip())


def _string_values(value: Any, field: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise InvalidBatchRequest(f"{field} must be a string or a list of strings")


def _bounded_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidBatchRequest(f"{field} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise InvalidBatchRequest(f"{field} must be between {minimum} and {maximum}")
    return parsed


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise InvalidBatchRequest(f"{field} must be true or false")


def _dedupe(values: Any) -> list[str]:
    return list(dict.fromkeys(values))


def _default_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("batch-%Y%m%dT%H%M%SZ")


def _fetch_json(url: str, *, timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise RuntimeError("YouTube API response exceeded the safety limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("YouTube API response was not a JSON object")
    if payload.get("error"):
        message = str((payload["error"] or {}).get("message") or "unknown API error")
        raise RuntimeError(f"YouTube API error: {message}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitube-batch",
        description=(
            "Fetch transcript, description, metadata, and comments for multiple "
            "YouTube videos or playlists."
        ),
    )
    parser.add_argument("request", type=Path, help="Batch request JSON path")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument(
        "--youtube-api-key",
        default=os.environ.get("YOUTUBE_API_KEY"),
        help="YouTube Data API key; defaults to YOUTUBE_API_KEY",
    )
    parser.add_argument(
        "--fast-cloud",
        action="store_true",
        help="Use the dependency-free GitHub cloud path",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        receipt, destination = run_batch(
            request,
            args.output,
            youtube_api_key=args.youtube_api_key,
            fast_cloud=args.fast_cloud,
        )
    except Exception as exc:
        print(f"AITubeTranscript batch failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"BATCH_ID={receipt['batch_id']}")
        print(f"BATCH_STATUS={receipt['status']}")
        print(f"VIDEO_COUNT={receipt['resolved_video_count']}")
        print(f"PROVEN_COUNT={receipt['proven_count']}")
        print(f"PARTIAL_COUNT={receipt['partial_count']}")
        print(f"FAILED_COUNT={receipt['failed_count']}")
        print(f"OUTPUT_DIR={destination}")

    return 0 if receipt["status"] == "PROVEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
