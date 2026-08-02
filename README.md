# AITubeTranscript

**Private-first YouTube research for humans and GPT agents.** Fetch a video's available transcript, full description, metadata, and a bounded set of top-level comments; store the result privately; and prove that every retrieved segment and comment is represented exactly once.

The source code is public. The supported GitHub workflow refuses public callers so requests, logs, transcripts, descriptions, comments, and receipts stay in a private companion repository.

## What it produces

Each private result is written to:

```text
aitube-results/videos/<video-id>/latest/
```

```text
latest/
├── reader-manifest.json
├── receipt.json
├── description.md
├── transcript.md
├── transcript.txt
├── transcript.jsonl
├── transcript-manifest.json
├── chunks/
│   ├── 001.md
│   └── ...
├── comments.md
├── comments.jsonl
├── comments-manifest.json
├── comment-chunks/
│   ├── 001.md
│   └── ...
└── result.json
```

`reader-manifest.json` is the entry point for an automated reader. It lists the exact bounded files to open, their deterministic order, and groups that may be read in parallel.

## Fast private GitHub setup

### 1. Create a private companion repository

Generated research must not be stored in this public repository. Create a private repository under your own account or organization.

### 2. Add one repository secret

In the private repository, create an Actions secret named:

```text
YOUTUBE_API_KEY
```

Use your own YouTube Data API key. Do not commit or paste the key into issues, workflow files, transcripts, or chat.

### 3. Add the private caller workflow

Create `.github/workflows/aitube.yml` in the private repository:

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
        description: Comma-separated language priority
        required: false
        default: en
        type: string
      comments:
        description: Maximum top-level comments
        required: false
        default: "100"
        type: string
      whisper:
        description: Use Whisper only when captions are unavailable
        required: false
        default: false
        type: boolean

permissions:
  contents: write

jobs:
  fetch:
    uses: organicoverlords/AITubeTranscript/.github/workflows/fetch.yml@main
    with:
      video_url: ${{ inputs.video_url }}
      languages: ${{ inputs.languages }}
      comments: ${{ inputs.comments }}
      whisper: ${{ inputs.whisper }}
    secrets:
      YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
```

Run **Private YouTube research** from the private repository's Actions page. The optimized cloud path uses the runner's existing Python runtime, shallow-checks out only this small public tool, verifies coverage, and shallow-fetches only the required private result path before publishing.

## GPT-optimized operation

For an agent with GitHub access, use a stable private request branch and one request file instead of creating a pull request for every video:

```text
request branch: request/aitube-live
request file:   aitube-requests/current.json
results branch: aitube-results
```

Canonical agent instructions:

- [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) — exact request, polling, proof, reading, timing, fallback, and privacy contract.
- [`GPT_MEMORY.md`](GPT_MEMORY.md) — copy-paste memory instructions, including a prefilled deployment and a generic template.

The core rule is simple: **workflow success is not proof that every word was read**. GPT must verify the manifests and actually open every file listed in `reader-manifest.json` before claiming complete reading.

## Proof contract

A retrieved transcript may be claimed as completely represented only when:

```text
receipt.transcript_status = PROVEN
receipt.transcript_coverage_status = PROVEN
transcript-manifest.coverage.status = PROVEN
transcript-manifest.coverage.exactly_once = true
```

The transcript coverage manifest must also show:

```text
missing_indices = []
duplicate_indices = []
unexpected_indices = []
ordered_contiguous = true
```

When comments were requested, apply the equivalent requirements to `comments_status`, `comments_coverage_status`, and `comments-manifest.json`.

This proves **retrieval representation**, not perfect transcription accuracy. Automatic captions and third-party transcript providers can contain repeated words, punctuation defects, and incorrect names. Important quotations should be checked against the original video.

## Retrieval strategy

The optimized GitHub path prioritizes low-latency cloud-compatible sources:

1. official YouTube Data API for description, metadata, and comments
2. available caption and public transcript endpoints
3. repository fallback ladder when the fast path fails
4. optional Whisper only when captions cannot be retrieved

The standard local path additionally supports `youtube-transcript-api`, `yt-dlp`, Deno/EJS challenge solving, cookies, proxies, and Whisper.

Every attempt and selected source is recorded in `receipt.json`. Missing data remains `NOT_PROVEN`; it is never silently described as complete.

## Local CLI

Python 3.10 or newer:

```bash
pipx install git+https://github.com/organicoverlords/AITubeTranscript.git
aitube-transcript "https://www.youtube.com/watch?v=x8W_S9zmodk" \
  --languages en \
  --comments 100
```

Set the API key locally for reliable descriptions and comments:

```bash
export YOUTUBE_API_KEY="your-key"
```

Windows PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "your-key"
```

For a video without retrievable captions:

```bash
pipx install "git+https://github.com/organicoverlords/AITubeTranscript.git#egg=aitube-transcript[whisper]"
aitube-transcript VIDEO_URL --whisper --whisper-model tiny
```

Local outputs remain under `results/<video-id>/` unless the user deliberately uploads them.

## Cookies and restricted videos

For local use only, export Netscape-format cookies and pass:

```bash
aitube-transcript VIDEO_URL --cookies /path/to/cookies.txt
```

Never commit cookies. They can grant access to a YouTube account. Official private GitHub setup does not require or distribute cookies.

## Privacy boundaries

- Public repository: source, tests, documentation, reusable workflow.
- Private repository: request file, Actions logs, generated research, API secret.
- Public workflow execution: rejected.
- Transcript artifacts: not uploaded through GitHub Actions artifacts.
- API keys and cookies: never included in generated files.

A user can deliberately modify their own fork to publish data. This project enforces privacy for the official workflow and documented setup; it cannot prevent intentional publication by modified code.

## Legal and responsible use

Use the tool only for videos you are allowed to access. Respect copyright, privacy, YouTube's terms, and applicable law. The MIT license applies to this software, not to downloaded transcripts, descriptions, or comments.
