# Install the private GitHub setup

This mirrors the proven `organicoverlords` deployment:

```text
public tool:      organicoverlords/AITubeTranscript
private runner:   your private repository
request branch:   request/aitube-live
request file:     aitube-requests/current.json
results branch:   aitube-results
memory root:      memory/
retention root:   retention/
```

You do not need to fork the public repository.

## 1. Create one private repository

Example:

```text
YOUR_ACCOUNT/aitube-private
```

It stores private requests, workflow logs, immutable snapshots, transcripts, descriptions, comments, channel catalogs, memory indexes, and retention records.

## 2. Create the API key

In Google Cloud:

1. create or select a project;
2. enable **YouTube Data API v3**;
3. create an API key;
4. restrict it to YouTube Data API v3.

Do not put the key in a request, commit, issue, log, or chat.

## 3. Add the private secret

In the private repository:

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

Create:

```text
YOUTUBE_API_KEY
```

## 4. Install three files

Copy from the public repository:

```text
templates/private-aitube-request.yml
  → .github/workflows/private-aitube-request.yml

templates/private-aitube-memory-bank.yml
  → .github/workflows/private-aitube-memory-bank.yml

templates/aitube-request.json
  → aitube-requests/current.json
```

Commit them to `main`.

The request workflow is the normal production path. It must call the reusable batch workflow at the exact pinned AITubeTranscript commit supplied by the current template. Do not replace a full commit SHA with `main`.

The memory workflow is **manual repair-only**. Normal fetches already publish immutable snapshots, latest and best pointers, memory indexes, and retention records in one atomic transaction.

## 5. Create the request branch

Create this branch from the validated `main` commit:

```text
request/aitube-live
```

The workflow and request file must exist before creating the branch.

## 6. Enable Actions writes

Allow GitHub Actions to write repository contents. The private workflow needs this only to publish to `aitube-results`.

The GitHub connection used by ChatGPT must be able to:

- read the private repository;
- update the request file on `request/aitube-live`;
- read the private `aitube-results` branch.

It does not need the API-key value.

## 7. Run the first test

On `request/aitube-live`, replace the request file with:

```json
{
  "request_id": "first-test-001",
  "video_url": "https://www.youtube.com/watch?v=JsrwIGbuM8o",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

Commit directly to the request branch.

## 8. Verify the result

Open:

```text
batches/first-test-001/latest/batch-receipt.json
videos/JsrwIGbuM8o/pointers/best.json
videos/JsrwIGbuM8o/pointers/latest.json
memory/by-video-id/JsrwIGbuM8o.json
retention/manifest.json
```

Require:

```text
batch accounting coverage = PROVEN
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

Confirm that:

- the video has an immutable `snapshots/<key>/` directory;
- `best.json` and `latest.json` resolve to valid snapshots;
- the memory pointer contains `preferred_result_path`;
- the retention record contains `refresh_due_at` and `delete_or_refresh_by`;
- all generated material remains on the private branch.

## Normal use

For each new request:

1. check the memory bank first;
2. fetch only when stored material cannot satisfy the request;
3. update `aitube-requests/current.json` on `request/aitube-live`;
4. poll the matching batch receipt;
5. follow the preferred snapshot pointer;
6. verify proof and retention;
7. open every reader file before claiming complete reading.

Request examples are in [`BATCH_USAGE.md`](BATCH_USAGE.md). GPT rules are in [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md).

## Manual memory repair

Run **Private AITube memory repair** manually only when indexes or pointers need rebuilding. It shares the same result-branch concurrency lock as normal publishing.

Do not configure it as an automatic `workflow_run` task.

## API retention

New API-backed snapshots record a conservative refresh and delete-or-refresh deadline. The current system exposes the deadlines but does not yet claim automated refresh or purge.

Review [`YOUTUBE_DATA_RETENTION.md`](YOUTUBE_DATA_RETENTION.md) and act before the recorded deadline.

## Common failures

### Workflow does not start

Confirm the change was committed to:

```text
request/aitube-live
```

and the path is exactly:

```text
aitube-requests/current.json
```

### Publication fails

Confirm Actions has repository-content write permission and that `aitube-results` is not protected against the GitHub Actions writer.

### API-backed data fails

Confirm `YOUTUBE_API_KEY` exists and is restricted to YouTube Data API v3.

### Runtime imports fail

Confirm the private workflow uses the exact pinned AITubeTranscript commit from the latest template. Do not use a stale pin or mutable branch name.

## Existing `organicoverlords` deployment

```text
public tool:      organicoverlords/AITubeTranscript
private runner:   organicoverlords/all
request branch:   request/aitube-live
results branch:   aitube-results
secret:           YOUTUBE_API_KEY
```

It is upgraded in place; it does not need a fresh repository.
