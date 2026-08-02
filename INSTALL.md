# Install the private GitHub setup

This is the same basic architecture as the working `organicoverlords` deployment:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  your private repository
request branch:  request/aitube-live
request file:    aitube-requests/current.json
results branch:  aitube-results
```

You do **not** need to fork or modify the public tool repository.

## 1. Create a private repository

Create one private GitHub repository for requests, workflow logs, transcripts, descriptions, comments, and receipts.

Example:

```text
YOUR_ACCOUNT/aitube-private
```

For the existing deployment, this repository is:

```text
organicoverlords/all
```

## 2. Create the YouTube API key

In Google Cloud:

1. Create or select a project.
2. Enable **YouTube Data API v3**.
3. Create an API key.
4. Restrict the key to **YouTube Data API v3**.

The key is used for reliable descriptions, metadata, and comments. Do not put it in the public repository or request file.

## 3. Add the key to the private repository

In the private GitHub repository, open:

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

Create this secret:

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

## 5. Create the request branch

Create this branch from the private repository's current `main` branch:

```text
request/aitube-live
```

The workflow and request file must already exist before creating the branch.

## 6. Give GPT access to the private repository

The GitHub connection used by GPT must be able to:

- read the private repository
- update `aitube-requests/current.json`
- read the private `aitube-results` branch

Do not give GPT the API key itself. GPT only needs repository access; GitHub Actions reads the secret.

## 7. Run the first video

Open this file on branch `request/aitube-live`:

```text
aitube-requests/current.json
```

Replace it with a real request:

```json
{
  "request_id": "first-test-001",
  "video_url": "https://www.youtube.com/watch?v=JsrwIGbuM8o",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

Commit the change directly to `request/aitube-live`.

That commit starts the private workflow automatically.

## 8. Check the result

The workflow creates or updates this private branch:

```text
aitube-results
```

The result is stored at:

```text
videos/<video-id>/latest/
```

For the example above:

```text
videos/JsrwIGbuM8o/latest/
```

Open `receipt.json` and require:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

Then use `reader-manifest.json` to read the description, transcript chunks, and comment chunks.

## Normal future use

After installation, each new video requires only one change:

1. Read the current blob SHA of `aitube-requests/current.json` on `request/aitube-live`.
2. Replace the file with a unique `request_id` and the new YouTube URL.
3. Poll the matching private receipt on `aitube-results`.
4. Verify coverage and read every file listed by `reader-manifest.json`.

The recommended GPT memory block is in [`GPT_MEMORY.md`](GPT_MEMORY.md).

## Three common problems

### Workflow does not start

Confirm that the request was committed to:

```text
request/aitube-live
```

and that the changed path is exactly:

```text
aitube-requests/current.json
```

### Publishing to `aitube-results` fails

The private workflow needs permission to write repository contents. Enable read/write workflow permissions for the private repository's GitHub Actions.

### Description or comments are not proven

Confirm that the private repository contains a valid `YOUTUBE_API_KEY` secret and that the key is allowed to use YouTube Data API v3.

## Existing `organicoverlords` setup

The current working deployment is already installed:

```text
public tool:     organicoverlords/AITubeTranscript
private runner:  organicoverlords/all
request branch:  request/aitube-live
results branch:  aitube-results
secret:          YOUTUBE_API_KEY
```

It does not need to be reinstalled. Future GPT requests should use [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md).
