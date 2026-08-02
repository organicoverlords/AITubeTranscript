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

Install:

- one-video, multi-video, playlist, and channel research
- private result publication
- a permanent private GitHub memory bank
- stable video-ID lookup paths
- logical download names containing date, channel, title, and video ID

## First MagicMusic run

Use one self-contained PowerShell payload to:

1. Verify Windows, Git, GitHub CLI, `gh auth status`, and the authenticated GitHub username.
2. Work in a temporary directory. Never edit the MagicMusic runner repository.
3. Create `<authenticated-user>/aitube-private` when absent, or verify that the existing repository is private.
4. Clone that private repository and verify its remote, branch, HEAD, and clean working tree before writing.
5. Copy these current public templates:
   - `organicoverlords/AITubeTranscript/templates/private-aitube-request.yml`
   - `organicoverlords/AITubeTranscript/templates/private-aitube-memory-bank.yml`
   - `organicoverlords/AITubeTranscript/templates/aitube-request.json`
6. Install them as:
   - `.github/workflows/private-aitube-request.yml`
   - `.github/workflows/private-aitube-memory-bank.yml`
   - `aitube-requests/current.json`
7. Verify that the request workflow calls the reusable private `batch-fetch.yml` workflow and that the memory workflow runs after **Private AITube fetch** and supports manual dispatch.
8. Commit and push all files to `main`.
9. Create and push `request/aitube-live` from that exact `main` commit.
10. Configure GitHub Actions to allow repository-content writes.
11. Verify remotely that:
    - the repository is private
    - `main` and `request/aitube-live` exist
    - all three installed files exist
    - the request workflow watches `request/aitube-live`
    - the memory workflow writes only to private `aitube-results`
    - generated research and memory indexes never go to the public source repository
12. Print a compact proof receipt. Never print tokens or secrets.

Fail closed on authentication failure, repository identity mismatch, public visibility, dirty-state risk, stale template content, or unexpected existing files.

## Only manual step

Open these pages for the user:

- Google Cloud Console for enabling **YouTube Data API v3** and creating an API key
- `https://github.com/<authenticated-user>/aitube-private/settings/secrets/actions/new`

Tell the user to restrict the key to YouTube Data API v3 and save it under:

```text
YOUTUBE_API_KEY
```

Never ask the user to paste the key into chat or a MagicMusic payload. Stop here and ask them to reply:

```text
secret added
```

## Verification after `secret added`

Use a second self-contained `# magicmusic-run` payload to:

1. Re-verify repository identity, privacy, branches, current workflow templates, and secret-name existence without reading the secret value.
2. Update `aitube-requests/current.json` on `request/aitube-live` with a unique timestamped request for:

```text
https://www.youtube.com/watch?v=JsrwIGbuM8o
```

Use English, 100 comments, and `whisper: false`.

3. Commit and push directly to `request/aitube-live`.
4. Poll the new private batch receipt under `aitube-results/batches/<request-id>/latest/`.
5. Require:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

6. Verify batch, transcript, comment, and reader manifests. Accounting and content coverage must be exactly once, ordered, contiguous, and contain no missing, duplicate, or unexpected indices.
7. Wait for or manually run **Private AITube memory bank**.
8. Require these private memory files:

```text
memory/bank-manifest.json
memory/video-index.jsonl
memory/by-video-id/JsrwIGbuM8o.json
videos/JsrwIGbuM8o/latest/memory-entry.json
videos/JsrwIGbuM8o/latest/download-name.txt
```

9. Verify that the memory pointer leads to the same private receipt and reader manifest.
10. Verify the logical download name follows:

```text
YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory
```

11. Confirm existing private results can be backfilled by manually dispatching the memory workflow.
12. Report the private repository, commits, branches, workflow results, counts, proof fields, memory index counts, stable paths, and logical name. Mark unsupported claims as `BLOCKED` or `NOT_PROVEN`.

Do not publish generated content, memory indexes, or logs to the public repository.

## Finish

After the test is proven, customize and give the user the persistent memory instruction from:

```text
organicoverlords/AITubeTranscript/GPT_MEMORY.md
```

Tell the user that permanent memory rules are in:

```text
organicoverlords/AITubeTranscript/MEMORY_BANK.md
```

Do not ask whether to continue. Continue automatically until the manual secret step, a genuine hard blocker, or fully proven completion.
