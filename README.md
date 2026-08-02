# AITubeTranscript

Fetch a YouTube video's **full available transcript**, metadata, description, and a bounded sample of comments. Every run writes human-readable files plus machine-readable proof receipts.

The source code is public and reusable. **Supported GitHub execution is private-only:** requests, workflow logs, transcripts, descriptions, comments, and receipts must live in a private companion repository.

## Privacy model

The official GitHub Action and reusable workflow refuse to run when the caller repository is public.

- The public repository contains source code, tests, and documentation only.
- The public repository has no issue-triggered or manually dispatched video-fetch workflow.
- The former public live-video smoke test has been replaced with a static privacy regression test.
- Private callers publish generated bundles only to their own private `aitube-results` branch.
- Local CLI and Docker runs remain local unless the user deliberately uploads their outputs.

A user can always modify code in their own fork. This project can enforce privacy for the official workflows and supported setup, but it cannot prevent someone from intentionally writing a different workflow that publishes their own data.

## Retrieval ladder

Transcript retrieval runs first so unavailable metadata or comment services cannot delay a usable transcript:

1. `youtube-transcript-api` for manual or automatic captions.
2. Caption tracks exposed by `yt-dlp`, with Deno/EJS challenge solving and alternate non-web clients.
3. Hosted no-key transcript fallbacks when cloud IPs cannot reach YouTube captions directly.
4. Optional `faster-whisper` audio transcription when captions do not exist.

Metadata and comments use independent fallbacks:

1. Direct `yt-dlp` extraction.
2. Optional official YouTube Data API using `YOUTUBE_API_KEY`.
3. YouTube oEmbed for basic title/channel metadata.
4. Public Piped and Invidious APIs.

Each attempt and selected source is written to `receipt.json`. Missing data remains `NOT_PROVEN` rather than being represented as complete.

## Complete transcript consumption proof

Large transcript files can be truncated by API clients, chat connectors, or browser previews even when retrieval succeeded. Every successful run therefore produces three additional representations:

- `transcript.jsonl` contains exactly one canonical JSON record per segment.
- `chunks/001.md`, `chunks/002.md`, and so on contain bounded-size readable groups of whole segments.
- `transcript-manifest.json` records every chunk range and hash, the JSONL hash, missing or duplicated indices, ordering, and an `exactly_once` result.

Chunk files target at most 10,000 UTF-8 bytes and 40 segments. A single unusually large segment is kept whole and marked as an oversized single-segment chunk rather than silently split or omitted.

`receipt.json` hashes every generated file, including nested chunk files, and reports `transcript_coverage_status`. A transcript is safe to claim as completely represented when both conditions hold:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
```

## Private GitHub setup

Create a **private** companion repository and add an Actions secret named:

```text
YOUTUBE_API_KEY
```

Add this caller workflow to the private repository as `.github/workflows/aitube.yml`:

```yaml
name: Private YouTube research

on:
  workflow_dispatch:
    inputs:
      video_url:
        description: YouTube URL or video ID
        required: true
        type: string
      languages:
        description: Caption language priority
        required: false
        default: en
        type: string
      comments:
        description: Maximum top-level comments
        required: false
        default: "100"
        type: string

permissions:
  contents: write

jobs:
  fetch:
    uses: organicoverlords/AITubeTranscript/.github/workflows/fetch.yml@main
    with:
      video_url: ${{ inputs.video_url }}
      languages: ${{ inputs.languages }}
      comments: ${{ inputs.comments }}
    secrets:
      YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
```

Run it from the private repository's **Actions** page. Results are committed only to its private branch:

```text
aitube-results/videos/<video-id>/latest/
```

The private workflow does not upload transcript artifacts and does not print transcript text into logs.

## Fast local use

Python 3.10 or newer:

```bash
pipx install git+https://github.com/organicoverlords/AITubeTranscript.git
aitube-transcript "https://www.youtube.com/watch?v=x8W_S9zmodk" --languages en --comments 100
```

Outputs remain on the local machine:

```text
results/<video-id>/
├── transcript.md
├── transcript.txt
├── transcript.jsonl
├── transcript-manifest.json
├── chunks/
│   ├── 001.md
│   ├── 002.md
│   └── ...
├── description.md
├── comments.md
├── result.json
└── receipt.json
```

For videos without captions:

```bash
pipx install "git+https://github.com/organicoverlords/AITubeTranscript.git#egg=aitube-transcript[whisper]"
aitube-transcript VIDEO_URL --whisper --whisper-model tiny
```

For reliable descriptions and comments, set the API key locally without committing it:

```bash
export YOUTUBE_API_KEY="your-key"
aitube-transcript VIDEO_URL --comments 100
```

Windows PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "your-key"
aitube-transcript VIDEO_URL --comments 100
```

## Direct composite Action use

The composite Action also rejects public caller repositories:

```yaml
- uses: organicoverlords/AITubeTranscript@main
  id: youtube
  env:
    YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
  with:
    url: https://www.youtube.com/watch?v=x8W_S9zmodk
    languages: en,fi
    comments: 100
```

Prefer the reusable workflow because it automatically writes results to the private `aitube-results` branch.

## Docker

```bash
docker build -t aitube-transcript .
docker run --rm -v "$PWD/results:/app/results" aitube-transcript VIDEO_URL
```

## Cookies and restricted videos

Export a Netscape-format `cookies.txt` locally and pass:

```bash
aitube-transcript VIDEO_URL --cookies /path/to/cookies.txt
```

Never commit cookies. They can grant access to a YouTube account.

## Third-party fallback privacy

When direct YouTube retrieval fails, the tool may send only the public video ID and requested language to hosted transcript providers, Piped, the official Invidious instance registry, and eligible public Invidious instances. It never sends cookies or API keys to these fallback services. The chosen source is visible in the receipt.

## Repository protection

`main` includes CODEOWNERS, a destructive-change guard, SHA-256 integrity manifests, complete Git-bundle backups, and optional mirroring to a separate private repository. See `REPOSITORY_PROTECTION.md` for recovery controls.

## What the receipt proves

`receipt.json` includes:

- transcript and comment status (`PROVEN` or `NOT_PROVEN`)
- transcript coverage status (`PROVEN`, `REJECTED`, or `NOT_APPLICABLE`)
- selected transcript source
- segment, chunk, and comment counts
- failed fallback attempts and warnings
- SHA-256 hashes for every generated file

A successful command does not automatically mean every data class was retrieved. Read the receipt and transcript manifest statuses.

## Legal and responsible use

Use the tool for videos you are allowed to access. Respect copyright, privacy, YouTube's terms, and applicable law. Transcripts and comments remain content from their respective creators; the MIT license applies to this software, not to downloaded content.
