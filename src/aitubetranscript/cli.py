from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .output import write_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitube-transcript",
        description=(
            "Fetch a YouTube transcript, metadata, description, comments, and proof receipt."
        ),
    )
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--languages", default="en", help="Comma-separated language priority")
    parser.add_argument("--comments", type=int, default=100, help="Maximum top-level comments")
    parser.add_argument("--no-comments", action="store_true")
    parser.add_argument("--cookies", type=Path, help="Netscape cookies.txt path")
    parser.add_argument("--proxy", help="HTTP/HTTPS proxy URL")
    parser.add_argument(
        "--youtube-api-key",
        default=os.environ.get("YOUTUBE_API_KEY"),
        help="Optional YouTube Data API key; defaults to YOUTUBE_API_KEY",
    )
    parser.add_argument(
        "--fast-cloud",
        action="store_true",
        help="Use the dependency-free GitHub cloud path and skip blocked yt-dlp probes",
    )
    parser.add_argument(
        "--whisper", action="store_true", help="Transcribe audio when captions fail"
    )
    parser.add_argument("--whisper-model", default="tiny")
    parser.add_argument("--whisper-device", default="cpu")
    parser.add_argument("--whisper-compute-type", default="int8")
    parser.add_argument("--json", action="store_true", help="Print final result JSON to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    languages = tuple(
        item.strip() for item in args.languages.split(",") if item.strip()
    ) or ("en",)
    comment_limit = max(0, args.comments)
    include_comments = not args.no_comments

    try:
        if args.fast_cloud:
            if args.whisper or args.cookies or args.proxy:
                raise ValueError(
                    "--fast-cloud does not support Whisper, cookies, or a proxy; "
                    "use the standard path instead"
                )
            from .cloud_fast import fetch_youtube_cloud

            bundle = fetch_youtube_cloud(
                args.url,
                languages=languages,
                comment_limit=comment_limit,
                include_comments=include_comments,
                youtube_api_key=args.youtube_api_key,
            )
        else:
            from .fetcher import FetchOptions, fetch_youtube
            from .youtubejs import enrich_bundle_with_youtubejs

            options = FetchOptions(
                languages=languages,
                comment_limit=comment_limit,
                include_comments=include_comments,
                cookies=args.cookies,
                proxy=args.proxy,
                whisper=args.whisper,
                whisper_model=args.whisper_model,
                whisper_device=args.whisper_device,
                whisper_compute_type=args.whisper_compute_type,
                youtube_api_key=args.youtube_api_key,
            )
            bundle = fetch_youtube(args.url, options)
            enrich_bundle_with_youtubejs(
                bundle,
                options.comment_limit if options.include_comments else 0,
            )
        destination = write_bundle(bundle, args.output)
    except Exception as exc:
        print(f"AITubeTranscript failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2))
    else:
        status = "PROVEN" if bundle.transcript and bundle.transcript.segments else "NOT_PROVEN"
        print(f"VIDEO_ID={bundle.video_id}")
        print(f"TRANSCRIPT_STATUS={status}")
        print(f"COMMENTS_COUNT={len(bundle.comments)}")
        print(f"OUTPUT_DIR={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
