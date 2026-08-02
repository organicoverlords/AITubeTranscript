# AITubeTranscript

**Private-first YouTube research for humans and GPT agents.** Fetch a video's available transcript, full description, metadata, and a bounded set of top-level comments; store the result privately; and prove that every retrieved segment and comment is represented exactly once.

The source code is public. The supported GitHub workflow refuses public callers so requests, logs, transcripts, descriptions, comments, and receipts stay in a private companion repository.

## Start here

- **Easiest setup through ChatGPT + MagicMusic:** [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md)
- **Manual setup like the working `organicoverlords` deployment:** [`INSTALL.md`](INSTALL.md)
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

## Private GitHub installation

Use [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md) when MagicMusic is available. ChatGPT creates the private repository, installs the templates, creates the request branch, configures Actions permissions, and verifies the result. The user only performs the API-key secret step.

Use [`INSTALL.md`](INSTALL.md) for the equivalent manual setup.

The existing deployment already uses:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  organicoverlords/all
request branch:  request/aitube-live
results branch:  aitube-results
```

## GPT-optimized operation

GPT should update one private request file, poll one private receipt, verify the manifests, and read every file listed by `reader-manifest.json`.

The core rule is simple: **workflow success is not proof that every word was read**. GPT may claim complete reading only after it has opened every reader file and the coverage manifests are proven.

Use:

- [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) for the exact request, polling, proof, timing, fallback, and privacy contract.
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

When comments were requested, apply the equivalent requirements to `comments_status`, `comments_coverage_status`, and `comments-manifest.json`.

This proves **retrieval representation**, not perfect transcription accuracy. Automatic captions and third-party transcript providers can contain repeated words, punctuation defects, and incorrect names. Important quotations should be checked against the original video.

## Retrieval strategy

The optimized GitHub path prioritizes low-latency cloud-compatible sources:

1. official YouTube Data API for description, metadata, and comments
2. available caption and public transcript endpoints
3. repository fallback ladder when the fast path fails
4. optional Whisper only when captions cannot be retrieved

Every attempt and selected source is recorded in `receipt.json`. Missing data remains `NOT_PROVEN`; it is never silently described as complete.

## Optional local CLI

The private GitHub setup does not require a local installation. For local use, Python 3.10 or newer:

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

## Cookies and restricted videos

Cookies are supported only for deliberate local use:

```bash
aitube-transcript VIDEO_URL --cookies /path/to/cookies.txt
```

Never commit cookies. They can grant access to a YouTube account. The official private GitHub setup does not require or distribute them.

## Privacy boundaries

- Public repository: source, tests, documentation, templates, reusable workflow.
- Private repository: request file, Actions logs, generated research, API secret.
- Public workflow execution: rejected.
- Transcript artifacts: not uploaded through GitHub Actions artifacts.
- API keys and cookies: never included in generated files.

A user can deliberately modify their own fork to publish data. This project enforces privacy for the official workflow and documented setup; it cannot prevent intentional publication by modified code.

## Legal and responsible use

Use the tool only for videos you are allowed to access. Respect copyright, privacy, YouTube's terms, and applicable law. The MIT license applies to this software, not to downloaded transcripts, descriptions, or comments.
