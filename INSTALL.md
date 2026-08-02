# Install the private GitHub setup

This uses the same architecture as the working `organicoverlords` deployment:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  your private repository
request branch:  request/aitube-live
request file:    aitube-requests/current.json
results branch:  aitube-results
memory root:     aitube-results/memory/
```

You do **not** need to fork or modify the public tool repository.

The installed workflows support one video, many videos, playlists, channel catalogs, and a permanent private memory bank for future ChatGPT sessions.

## 1. Create a private repository

Create one private GitHub repository for requests, workflow logs, transcripts, descriptions, comments, channel catalogs, receipts, and memory indexes.

Example:

```text
YOUR_ACCOUNT/aitube-private
```

The existing deployment uses:

```text
organicoverlords/all
```

## 2. Create the YouTube API key

In Google Cloud:

1. Create or select a project.
2. Enable **YouTube Data API v3**.
3. Create an API key.
4. Restrict the key to **YouTube Data API v3**.

The key is used for playlist expansion, channel upload catalogs, descriptions, durations, publication metadata, statistics, and comments. Do not put it in the public repository or request file.

## 3. Add the key to the private repository

In the private GitHub repository, open:

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

Create:

```text
Name:  YOUTUBE_API_KEY
Value: your API key
```

You add it once. Future runs use it automatically.

## 4. Add the three private files

On the private repository's `main` branch, copy:

```text
AITubeTranscript/templates/private-aitube-request.yml
```

to:

```text
.github/workflows/private-aitube-request.yml
```

Copy:

```text
AITubeTranscript/templates/private-aitube-memory-bank.yml
```

to:

```text
.github/workflows/private-aitube-memory-bank.yml
```

Then copy:

```text
AITubeTranscript/templates/aitube-request.json
```

to:

```text
aitube-requests/current.json
```

Commit all three files to `main`.

The fetch workflow calls the reusable private batch workflow. The memory workflow runs after each fetch and can also be started manually to backfill existing results.

## 5. Create the request branch

Create this branch from the private repository's current `main` branch:

```text
request/aitube-live
```

The workflows and request file must exist before creating the branch.

## 6. Give GPT access to the private repository

The GitHub connection used by GPT must be able to:

- read the private repository
- update `aitube-requests/current.json`
- read the private `aitube-results` branch
- read the compact `memory/` indexes

Do not give GPT the API key itself. GitHub Actions reads the secret.

## 7. Run the first video

On `request/aitube-live`, replace `aitube-requests/current.json` with:

```json
{
  "request_id": "first-test-001",
  "video_url": "https://www.youtube.com/watch?v=JsrwIGbuM8o",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

Commit directly to `request/aitube-live`. That starts the private fetch workflow. The memory workflow runs after it completes.

## 8. Check the result and memory pointer

First open:

```text
batches/first-test-001/latest/batch-receipt.json
```

Then open:

```text
videos/JsrwIGbuM8o/latest/receipt.json
```

Require:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

The memory workflow should also create:

```text
memory/by-video-id/JsrwIGbuM8o.json
memory/video-index.jsonl
memory/video-index.md
videos/JsrwIGbuM8o/latest/memory-entry.json
videos/JsrwIGbuM8o/latest/download-name.txt
```

`download-name.txt` uses the logical format:

```text
YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory
```

Use stable video-ID paths for automation and logical names for downloaded folders or archives.

## Normal future use

For every request, GPT should:

1. Check the private memory bank first.
2. Reuse stored proven material when it satisfies the request.
3. Start a new fetch only for missing content, failed proof, changed language/comment requirements, current statistics, new comments, or an explicit refresh.
4. When fetching, update `aitube-requests/current.json` on `request/aitube-live` with a unique `request_id`.
5. Poll and verify the matching private receipt and manifests.
6. Let the post-fetch workflow update the permanent memory indexes.

Known video ID lookup:

```text
memory/by-video-id/<VIDEO_ID>.json
```

Title, channel, topic, or date lookup:

```text
memory/video-index.jsonl
```

Channel and batch lookup:

```text
memory/channel-index.jsonl
memory/batch-index.jsonl
```

Complete memory rules are in [`MEMORY_BANK.md`](MEMORY_BANK.md). The copy-paste persistent instruction is in [`GPT_MEMORY.md`](GPT_MEMORY.md).

## Common problems

### Fetch workflow does not start

Confirm the request was committed to `request/aitube-live` and the changed path is exactly `aitube-requests/current.json`.

### Publishing to `aitube-results` fails

Enable read/write workflow permissions for the private repository's GitHub Actions.

### Memory bank does not update

Run **Private AITube memory bank** manually from the private repository's Actions page. Confirm `aitube-results` exists and Actions has content write permission.

### Playlists, channels, descriptions, or comments fail

Confirm the private repository contains a valid `YOUTUBE_API_KEY` secret restricted to YouTube Data API v3.

## Existing `organicoverlords` setup

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  organicoverlords/all
request branch:  request/aitube-live
results branch:  aitube-results
memory root:     aitube-results/memory/
secret:          YOUTUBE_API_KEY
```

Future GPT requests should use [`MEMORY_BANK.md`](MEMORY_BANK.md) first and [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) only when a new fetch is required.
