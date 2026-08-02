# Install the private GitHub setup

This uses the same architecture as the working `organicoverlords` deployment:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  your private repository
request branch:  request/aitube-live
request file:    aitube-requests/current.json
results branch:  aitube-results
```

You do **not** need to fork or modify the public tool repository.

The installed workflow supports one video, many videos, playlists, and channel catalogs.

## 1. Create a private repository

Create one private GitHub repository for requests, workflow logs, transcripts, descriptions, comments, channel catalogs, and receipts.

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

## 4. Add the two private files

On the private repository's `main` branch, copy:

```text
AITubeTranscript/templates/private-aitube-request.yml
```

to:

```text
.github/workflows/private-aitube-request.yml
```

Then copy:

```text
AITubeTranscript/templates/aitube-request.json
```

to:

```text
aitube-requests/current.json
```

Commit both files to `main`.

The workflow template must call:

```text
organicoverlords/AITubeTranscript/.github/workflows/batch-fetch.yml@main
```

Do not use an older single-video-only template.

## 5. Create the request branch

Create this branch from the private repository's current `main` branch:

```text
request/aitube-live
```

The workflow and request file must exist before creating the branch.

## 6. Give GPT access to the private repository

The GitHub connection used by GPT must be able to:

- read the private repository
- update `aitube-requests/current.json`
- read the private `aitube-results` branch

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

Commit directly to `request/aitube-live`. That starts the private workflow.

## 8. Check the result

The workflow creates or updates:

```text
aitube-results
```

First open:

```text
batches/first-test-001/latest/batch-receipt.json
```

Require exactly-once batch accounting and locate the selected video result. Then open:

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

Use `batch-reader-manifest.json` and the video's `reader-manifest.json` to find every required file.

## Normal future use

For each new request:

1. Read the current blob SHA of `aitube-requests/current.json` on `request/aitube-live`.
2. Replace it with a unique `request_id` and one of the formats in [`BATCH_USAGE.md`](BATCH_USAGE.md).
3. Poll the matching private batch receipt.
4. Verify batch, channel, transcript, and comment coverage as applicable.
5. Read every file required by the relevant reader manifests.

Supported fields include:

```text
video_url / video_urls
playlist_url / playlist_urls
channel_url / channel_urls
```

A channel catalog request creates:

```text
channels/<channel-id>/latest/channel-videos.md
channels/<channel-id>/latest/channel-videos.jsonl
channels/<channel-id>/latest/channel-catalog.json
channels/<channel-id>/latest/channel-receipt.json
```

Each selected public upload includes its title, publication timestamp/date, duration, video ID/URL, and available snapshot statistics.

The recommended GPT memory block is in [`GPT_MEMORY.md`](GPT_MEMORY.md).

## Three common problems

### Workflow does not start

Confirm the request was committed to:

```text
request/aitube-live
```

and the changed path is exactly:

```text
aitube-requests/current.json
```

### Publishing to `aitube-results` fails

Enable read/write workflow permissions for the private repository's GitHub Actions.

### Playlists, channels, descriptions, or comments fail

Confirm the private repository contains a valid `YOUTUBE_API_KEY` secret restricted to YouTube Data API v3.

## Existing `organicoverlords` setup

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  organicoverlords/all
request branch:  request/aitube-live
results branch:  aitube-results
secret:          YOUTUBE_API_KEY
```

It does not need to be reinstalled. Future GPT requests should use [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md).
