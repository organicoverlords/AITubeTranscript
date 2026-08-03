# Install the private GitHub setup

Recommended architecture:

```text
public tool:             organicoverlords/AITubeTranscript
private runner:          your private repository
request branch:          request/aitube-live
request file:            aitube-requests/current.json
durable evidence branch: aitube-durable
volatile API branch:     aitube-volatile
legacy migration source: aitube-results
secret:                  YOUTUBE_API_KEY
```

You do not need to fork the public repository.

## 1. Create one private repository

Example:

```text
YOUR_ACCOUNT/aitube-private
```

It stores private requests and workflow logs plus two result branches:

- `aitube-durable`: transcript evidence and internal proof;
- `aitube-volatile`: API-derived descriptions, comments, metadata, catalogs, and retention state.

## 2. Create and store the API key

In Google Cloud:

1. create or select a project;
2. enable **YouTube Data API v3**;
3. create an API key;
4. restrict it to YouTube Data API v3.

In the private repository create the Actions secret:

```text
YOUTUBE_API_KEY
```

Never put the key in a request, commit, issue, log, script output, or chat.

## 3. Install the private files

Copy the latest pinned templates:

```text
templates/private-aitube-request.yml
  → .github/workflows/private-aitube-request.yml

templates/private-aitube-retention.yml
  → .github/workflows/private-aitube-retention.yml

templates/private-aitube-migrate.yml
  → .github/workflows/private-aitube-migrate.yml

templates/aitube-request.json
  → aitube-requests/current.json
```

Commit them to `main`.

The request workflow is the normal production path. It must call the reusable public workflows at exact full commit SHAs. Never replace an immutable pin with `main`, a tag, or a branch name.

The retention workflow is scheduled and manual. It evaluates and purges expired volatile API overlays.

The migration workflow is manual-only and is needed only when upgrading an existing `aitube-results` deployment.

## 4. Create the request branch

Create from the validated `main` commit:

```text
request/aitube-live
```

The request workflow and request file must exist on the branch before the first request.

## 5. Enable Actions writes

Allow GitHub Actions to write repository contents.

The workflows need to:

- append commits to `aitube-durable`;
- force-rewrite `aitube-volatile` as one parentless reachable commit;
- read `aitube-results` during one-time migration only.

Do not configure no-force protection on `aitube-volatile`. Instead restrict who can update it to the trusted Actions workflow and approved maintainers.

Protect `aitube-durable` against deletion and force pushes where repository rules permit.

## 6. GitHub access for ChatGPT

The GitHub connection used by ChatGPT should be able to:

- read the private repository;
- update `aitube-requests/current.json` on `request/aitube-live`;
- read `aitube-durable` and `aitube-volatile`.

It does not need to read the API-key value.

## 7. Run the first test

On `request/aitube-live`, replace the request with:

```json
{
  "request_id": "first-split-test-001",
  "video_url": "https://www.youtube.com/watch?v=JsrwIGbuM8o",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

Commit directly to the request branch.

## 8. Verify durable evidence

On `aitube-durable`, require:

```text
batches/first-split-test-001/latest/batch-receipt.json
memory/by-video-id/JsrwIGbuM8o.json
videos/JsrwIGbuM8o/pointers/best-transcript.json
videos/JsrwIGbuM8o/snapshots/<SNAPSHOT_KEY>/reader-manifest.json
videos/JsrwIGbuM8o/snapshots/<SNAPSHOT_KEY>/transcript-manifest.json
```

Require:

```text
batch accounting = PROVEN
transcript_status = PROVEN
transcript_coverage_status = PROVEN
```

Confirm the durable snapshot contains transcript chunks and does **not** contain:

```text
description.md
comments.md
comments-manifest.json
comment-chunks/
result.json
api-result.json
```

## 9. Verify the volatile overlay

On `aitube-volatile`, require:

```text
memory/by-video-id/JsrwIGbuM8o.json
videos/JsrwIGbuM8o/overlays/<SAME_SNAPSHOT_KEY>/overlay-metadata.json
videos/JsrwIGbuM8o/pointers/latest.json
videos/JsrwIGbuM8o/pointers/best-comments.json
retention/manifest.json
```

When 100 comments were available, require:

```text
comments_status = PROVEN
comments_coverage_status = PROVEN
comment_count >= 100
retention.status = CURRENT
```

Confirm the overlay refers back to the durable snapshot.

## 10. Test requirement-based selection

Check the stored video using:

```text
language=en
minimum comments=100
maximum API age=25 days
```

Require:

```text
selection_status = SATISFIED
```

The selector must return exact durable and volatile paths and explain the match.

## 11. Verify scheduled maintenance

Run the private retention workflow manually once after installation. Require:

```text
VOLATILE_RETENTION_MAINTENANCE=PROVEN
```

Confirm:

- the volatile retention manifest was rebuilt;
- current pointers still resolve;
- `aitube-volatile` has one reachable parentless commit after rewrite;
- no permanent artifact containing volatile API data was created.

Physical garbage collection of unreachable GitHub objects remains `NOT_INDEPENDENTLY_PROVEN`.

## Upgrade an existing `aitube-results` deployment

Run the manual split migration once. It checks out the currently materialized legacy branch and:

- copies transcript evidence to `aitube-durable`;
- copies API-derived data to `aitube-volatile`;
- marks inferred settings conservatively;
- migrates video, channel, and batch `latest/` bundles;
- does not refetch YouTube;
- does not claim recovery of variants surviving only in old Git history.

After proof, new requests must stop writing to `aitube-results`.

Keep the old branch only as an explicitly labeled legacy recovery source until the operator decides how to retire it. Deleting a branch does not itself prove physical deletion from GitHub storage.

## Backup policy

Back up `aitube-durable` independently.

Do not place `aitube-volatile` in an indefinite mirror, Git bundle, release asset, or immutable archive unless the backup system applies matching expiry and deletion controls.

## Common failures

### Workflow does not start

Confirm the request was committed to:

```text
request/aitube-live
```

and the path is exactly:

```text
aitube-requests/current.json
```

### Durable publication fails

Confirm Actions has content-write permission and `aitube-durable` permits the trusted Actions writer. Real commit failures are not ignored.

### Volatile rewrite fails

Confirm the workflow may force-update `aitube-volatile` and no branch rule blocks that rewrite.

### API-backed data fails

Confirm `YOUTUBE_API_KEY` exists and is restricted to YouTube Data API v3.

### Runtime imports fail

Confirm all private reusable workflow references and `tool_ref` values are full pinned commit SHAs from the latest templates.

## Existing `organicoverlords` deployment

```text
private repository: organicoverlords/all
request branch:     request/aitube-live
durable branch:     aitube-durable
volatile branch:    aitube-volatile
legacy branch:      aitube-results
secret:             YOUTUBE_API_KEY
```

It is upgraded in place through the one-time split migration.
