# Install through ChatGPT and MagicMusic

Your friend only needs to tell ChatGPT:

```text
Read organicoverlords/AITubeTranscript/MAGICMUSIC_INSTALL.md and follow it completely. Use my authenticated GitHub account and continue until you reach the API-key step or the installation is proven.
```

## Instructions for ChatGPT

Use the exact MagicMusic command prefix:

```text
# magicmusic-run
```

MagicMusic is only the local PowerShell runner. You must plan the installation, generate the scripts, validate every result, and report proof. Do not give the user a long manual checklist.

The installed request workflow must support:

- one YouTube video
- several video URLs in one request
- one or several playlists
- one or several channel catalogs
- optional full research for selected channel uploads

Channel catalogs must list titles, publication timestamps/dates, durations, video IDs/URLs, and available snapshot statistics.

## First MagicMusic run

Use one self-contained PowerShell payload to:

1. Verify Windows, Git, GitHub CLI, `gh auth status`, and the authenticated GitHub username.
2. Work in a temporary directory. Never edit the MagicMusic runner repository.
3. Create `<authenticated-user>/aitube-private` when absent, or verify that the existing repository is private.
4. Clone that private repository and verify its remote, branch, HEAD, and clean working tree before writing.
5. Copy these current public templates:
   - `organicoverlords/AITubeTranscript/templates/private-aitube-request.yml`
   - `organicoverlords/AITubeTranscript/templates/aitube-request.json`
6. Install them in the private repository as:
   - `.github/workflows/private-aitube-request.yml`
   - `aitube-requests/current.json`
7. Verify that the installed workflow calls the reusable private `batch-fetch.yml` workflow. Do not install an older single-video-only template.
8. Commit and push the files to `main`.
9. Create and push `request/aitube-live` from that exact `main` commit.
10. Configure GitHub Actions to allow repository-content writes.
11. Verify remotely that:
    - the repository is private
    - both branches exist
    - both files exist
    - the workflow watches `request/aitube-live`
    - the workflow passes the complete request JSON to `batch-fetch.yml`
    - generated videos, batches, and channel catalogs go only to `aitube-results`
12. Print a compact proof receipt. Never print tokens or secrets.

Fail closed on authentication failure, repository identity mismatch, public visibility, dirty-state risk, stale template content, or unexpected existing files.

## Only manual step

After repository setup, open these pages for the user:

- Google Cloud Console for enabling **YouTube Data API v3** and creating an API key
- `https://github.com/<authenticated-user>/aitube-private/settings/secrets/actions/new`

Tell the user to restrict the key to YouTube Data API v3 and save it under the exact secret name:

```text
YOUTUBE_API_KEY
```

The key enables playlist expansion, channel upload catalogs, descriptions, durations, publication metadata, statistics, and comments.

Never ask the user to paste the key into chat or a MagicMusic payload. Stop here and ask them to reply:

```text
secret added
```

## Verification after `secret added`

Use a second self-contained `# magicmusic-run` payload to:

1. Re-verify repository identity, privacy, branches, workflow version, and secret-name existence without reading the secret value.
2. Update `aitube-requests/current.json` on `request/aitube-live` with a unique timestamped request for:

```text
https://www.youtube.com/watch?v=JsrwIGbuM8o
```

Use English, 100 comments, and `whisper: false`.

3. Commit and push directly to `request/aitube-live`.
4. Wait for the private workflow and poll the new batch receipt:

```text
aitube-results/batches/<request-id>/latest/batch-receipt.json
```

5. From that receipt, locate the selected video's private result and require:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

6. Verify `batch-reader-manifest.json`, `reader-manifest.json`, `transcript-manifest.json`, and `comments-manifest.json`. Accounting and content coverage must be exactly once, ordered, contiguous, and have no missing, duplicate, or unexpected indices.
7. Confirm every required file is privately readable.
8. Confirm the installed request parser accepts `video_urls`, `playlist_url(s)`, and `channel_url(s)` by reading the current public `BATCH_USAGE.md` and workflow template. Do not start a large batch merely to prove parsing.
9. Report the private repository, commits, branches, workflow result, counts, coverage status, private result path, and installed batch/channel capabilities. Mark unsupported claims as `BLOCKED` or `NOT_PROVEN`.

Do not publish generated content or logs to the public repository.

## Finish

After the test is proven, customize and give the user the persistent ChatGPT memory instruction from:

```text
organicoverlords/AITubeTranscript/GPT_MEMORY.md
```

Also tell the user that request examples are in:

```text
organicoverlords/AITubeTranscript/BATCH_USAGE.md
```

Do not ask whether to continue. Continue automatically until the manual secret step, a genuine hard blocker, or fully proven completion.
