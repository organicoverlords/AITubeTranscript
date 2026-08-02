# AITubeTranscript

**Private-first YouTube research for humans and GPT agents.** Fetch one video, many videos, playlists, or channel catalogs; keep generated research private; and prove exactly what was retrieved and read.

AITubeTranscript collects transcripts, descriptions, metadata, and bounded top-level comments. It does **not** download or republish video or audio files.

The source code is public. Official GitHub workflows reject public callers so requests, logs, transcripts, descriptions, comments, catalogs, and receipts remain in a private companion repository.

## Start here

- **Easiest setup through ChatGPT + MagicMusic:** [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md)
- **Multiple videos, playlists, and channels:** [`BATCH_USAGE.md`](BATCH_USAGE.md)
- **Manual private setup:** [`INSTALL.md`](INSTALL.md)
- **Canonical GPT execution contract:** [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md)
- **Copy-paste ChatGPT memory instruction:** [`GPT_MEMORY.md`](GPT_MEMORY.md)

For the easiest setup, tell ChatGPT only:

```text
Read organicoverlords/AITubeTranscript/MAGICMUSIC_INSTALL.md and follow it completely. Use my authenticated GitHub account and continue until you reach the API-key step or the installation is proven.
```

The recommended architecture is intentionally simple:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  one private repository
request branch:  request/aitube-live
request file:    aitube-requests/current.json
results branch:  aitube-results
```

You do not need to fork or modify this public repository.

## Supported private requests

The same request file supports:

- one `video_url`
- several `video_urls`
- one or several `playlist_url(s)`
- one or several `channel_url(s)`
- any mixture of those sources

Example channel catalog request:

```json
{
  "request_id": "channel-catalog-20260803-001",
  "channel_url": "https://www.youtube.com/@CHANNEL_HANDLE",
  "channel_start_index": 0,
  "catalog_max_videos": 5000,
  "research_channel_videos": false
}
```

A channel catalog lists every selected public API-visible upload with:

- title and video URL
- exact publication timestamp and date
- ISO duration, seconds, and readable duration
- snapshot views, likes, and comments
- privacy/API visibility and live status

Set `research_channel_videos` to `true` to also fetch full transcript, description, metadata, and comment bundles for up to `max_videos` selected uploads.

See [`BATCH_USAGE.md`](BATCH_USAGE.md) for complete examples, continuation offsets, limits, and proof rules.

## Private result paths

### Individual video

```text
videos/<video-id>/latest/
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
├── comments.md
├── comments.jsonl
├── comments-manifest.json
├── comment-chunks/
└── result.json
```

### Channel catalog

```text
channels/<channel-id>/latest/
├── channel-receipt.json
├── channel-videos.md
├── channel-videos.jsonl
└── channel-catalog.json
```

### Batch receipt

```text
batches/<request-id>/latest/
├── batch-receipt.json
└── batch-reader-manifest.json
```

The batch receipt accounts for every selected video, playlist expansion, channel catalog, duplicate removal, partial result, and failure.

## Private GitHub installation

Use [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md) when MagicMusic is available. ChatGPT creates the private repository, installs the current batch-capable request workflow, creates the request branch, configures Actions permissions, and verifies the result. The user performs only the API-key secret step.

Use [`INSTALL.md`](INSTALL.md) for the equivalent manual setup.

The existing deployment uses:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  organicoverlords/all
request branch:  request/aitube-live
results branch:  aitube-results
```

## GPT-optimized operation

GPT updates one private request file, polls one private receipt, verifies the manifests, and opens every file required by the appropriate reader manifest.

Workflow success is not proof that every word was read. GPT may claim complete reading only after it has opened every required reader file and the relevant coverage manifests are proven.

Use:

- [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) for exact request, polling, batch, catalog, proof, timing, fallback, and privacy rules.
- [`GPT_MEMORY.md`](GPT_MEMORY.md) for the stable instruction to save in ChatGPT memory.

## Proof contract

A transcript may be claimed as completely represented only when:

```text
receipt.transcript_status = PROVEN
receipt.transcript_coverage_status = PROVEN
transcript-manifest.coverage.status = PROVEN
transcript-manifest.coverage.exactly_once = true
```

The coverage manifest must also show:

```text
missing_indices = []
duplicate_indices = []
unexpected_indices = []
ordered_contiguous = true
```

Apply the equivalent requirements to comments when requested. Batch and channel receipts independently prove ordered, exactly-once accounting of selected rows; a catalog or playlist may still be `PARTIAL` when deliberately truncated or when a private/deleted video has no public details.

Retrieval representation is different from transcription accuracy. Automatic captions and third-party transcript providers can contain repeated words, punctuation defects, and incorrect names. Important quotations should be checked against the original video.

## Retrieval strategy

The optimized GitHub path uses:

1. YouTube Data API for playlists, channel uploads, descriptions, durations, publication dates, statistics, and comments
2. available caption and public transcript endpoints
3. repository fallback sources when the fast path fails
4. optional Whisper only when captions cannot be retrieved

Every attempt and selected source is recorded. Missing data remains `NOT_PROVEN`; it is never silently described as complete.

## Optional local CLI

The private GitHub setup requires no local Python installation. For local use with Python 3.10 or newer:

```bash
pipx install git+https://github.com/organicoverlords/AITubeTranscript.git
```

One video:

```bash
aitube-transcript VIDEO_URL --languages en --comments 100
```

Batch request file:

```bash
aitube-batch request.json --fast-cloud
```

Channel catalog:

```bash
aitube-channel "https://www.youtube.com/@CHANNEL_HANDLE" --max-videos 5000
```

Set the API key locally for playlists, channel catalogs, reliable descriptions, and comments:

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

## Privacy boundaries

- Public repository: source, tests, documentation, templates, reusable workflows.
- Private repository: request files, Actions logs, generated research, channel catalogs, receipts, API secret.
- Public workflow execution: rejected.
- Generated research is not uploaded as public GitHub Actions artifacts.
- API keys and cookies are never included in generated files.

A user can deliberately modify their own fork to publish data. This project enforces privacy for the official workflow and documented setup; it cannot prevent intentional publication by modified code.

## Legal and responsible use

Use the tool only for content you are allowed to access. Respect copyright, privacy, YouTube's terms, and applicable law. The MIT license applies to this software, not to retrieved transcripts, descriptions, comments, or channel metadata.
