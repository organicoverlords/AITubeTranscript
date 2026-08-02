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

### First MagicMusic run

Use one self-contained PowerShell payload to:

1. Verify Windows, Git, GitHub CLI, `gh auth status`, and the authenticated GitHub username.
2. Work in a temporary directory. Never edit the MagicMusic runner repository.
3. Create `<authenticated-user>/aitube-private` when absent, or verify that the existing repository is private.
4. Clone that private repository and verify its remote, branch, HEAD, and clean working tree before writing.
5. Copy these public templates:
   - `organicoverlords/AITubeTranscript/templates/private-aitube-request.yml`
   - `organicoverlords/AITubeTranscript/templates/aitube-request.json`
6. Install them in the private repository as:
   - `.github/workflows/private-aitube-request.yml`
   - `aitube-requests/current.json`
7. Commit and push them to `main`.
8. Create and push `request/aitube-live` from that exact `main` commit.
9. Configure GitHub Actions to allow repository-content writes.
10. Verify remotely that:
    - the repository is private
    - both branches exist
    - both files exist
    - the workflow watches `request/aitube-live`
    - generated results will go to `aitube-results`
11. Print a compact proof receipt. Never print tokens or secrets.

Fail closed on authentication failure, repository identity mismatch, public visibility, dirty-state risk, or unexpected existing files.

### Only manual step

After repository setup, open these pages for the user:

- Google Cloud Console for enabling **YouTube Data API v3** and creating an API key
- `https://github.com/<authenticated-user>/aitube-private/settings/secrets/actions/new`

Tell the user to restrict the key to YouTube Data API v3 and save it under the exact secret name:

```text
YOUTUBE_API_KEY
```

Never ask the user to paste the key into chat or a MagicMusic payload. Stop here and ask them to reply:

```text
secret added
```

### Verification after `secret added`

Use a second self-contained `# magicmusic-run` payload to:

1. Re-verify repository identity and privacy.
2. Update `aitube-requests/current.json` on `request/aitube-live` with a unique timestamped request for:

```text
https://www.youtube.com/watch?v=JsrwIGbuM8o
```

Use English, 100 comments, and `whisper: false`.

3. Commit and push the request directly to `request/aitube-live`.
4. Wait for the private workflow and poll:

```text
aitube-results/videos/JsrwIGbuM8o/latest/receipt.json
```

5. Require:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN
comments_coverage_status = PROVEN
```

6. Verify `reader-manifest.json`, `transcript-manifest.json`, and `comments-manifest.json`. Both coverage manifests must show exactly-once, ordered, contiguous coverage with no missing, duplicate, or unexpected indices.
7. Confirm every file named by `reader-manifest.json` is privately readable.
8. Report the private repository, commits, branches, workflow result, counts, coverage status, and private result path. Mark anything unsupported as `BLOCKED` or `NOT_PROVEN`.

Do not publish generated content or logs to the public repository.

### Finish

After the test is proven, customize and give the user the persistent ChatGPT memory instruction from:

```text
organicoverlords/AITubeTranscript/GPT_MEMORY.md
```

Do not ask whether to continue. Continue automatically until the manual secret step, a genuine hard blocker, or fully proven completion.
