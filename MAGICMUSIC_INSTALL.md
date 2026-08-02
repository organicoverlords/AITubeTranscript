# Install through ChatGPT and MagicMusic

Your friend only needs to tell ChatGPT:

```text
Read organicoverlords/AITubeTranscript/MAGICMUSIC_INSTALL.md and follow it completely. Use my authenticated GitHub account and continue until you reach the API-key step or the installation is proven.
```

## Instructions for ChatGPT

Use the exact command prefix:

```text
# magicmusic-run
```

MagicMusic is only the local PowerShell runner. ChatGPT must plan the installation, generate safe scripts, validate every result, and report proof. Do not give the user a long manual checklist.

## Target architecture

```text
public tool:      organicoverlords/AITubeTranscript
private repo:     <authenticated-user>/aitube-private
main branch:      main
request branch:   request/aitube-live
request file:     aitube-requests/current.json
results branch:   aitube-results
secret:           YOUTUBE_API_KEY
```

The installed system must support:

- one or many videos;
- playlists;
- channel catalogs with names, publication dates, durations, IDs, URLs, and available statistics;
- immutable snapshots;
- separate latest and best pointers;
- permanent private memory indexes;
- API retention records;
- manual memory repair.

## First MagicMusic payload

Use one self-contained PowerShell payload to:

1. verify Windows, Git, GitHub CLI, `gh auth status`, and the authenticated username;
2. work outside the MagicMusic runner repository;
3. create `<username>/aitube-private` when absent, or prove the existing repository is private;
4. clone and verify repository identity, remote, branch, HEAD, and clean working tree;
5. download the current public templates:
   - `templates/private-aitube-request.yml`
   - `templates/private-aitube-memory-bank.yml`
   - `templates/aitube-request.json`
6. install them as:
   - `.github/workflows/private-aitube-request.yml`
   - `.github/workflows/private-aitube-memory-bank.yml`
   - `aitube-requests/current.json`
7. verify all third-party Actions and reusable workflows use full immutable commit SHAs;
8. verify the request workflow calls the current snapshot-capable `batch-fetch.yml` and passes its exact pinned tool commit;
9. verify the memory workflow is `workflow_dispatch` only and cannot run automatically through `workflow_run`;
10. commit and push the files to `main`;
11. create and push `request/aitube-live` from that exact commit;
12. enable repository-content writes for Actions;
13. prove remotely that the repository remains private and both branches and all three files exist;
14. print a compact receipt without tokens or secrets.

Fail closed on authentication failure, public visibility, repository mismatch, dirty-state risk, mutable workflow references, stale templates, or unexpected existing files.

## Only manual step

Open:

- Google Cloud Console for enabling YouTube Data API v3 and creating a restricted API key;
- `https://github.com/<authenticated-user>/aitube-private/settings/secrets/actions/new`.

Tell the user to save the key with the exact name:

```text
YOUTUBE_API_KEY
```

Never ask them to paste the key into chat or MagicMusic. Pause and ask them to reply:

```text
secret added
```

## Verification after `secret added`

Use a second self-contained `# magicmusic-run` payload to:

1. re-verify repository identity, privacy, branches, pinned workflow references, and secret-name existence without reading the secret;
2. update the request file on `request/aitube-live` with a unique request for:

```text
https://www.youtube.com/watch?v=JsrwIGbuM8o
```

Use English, 100 comments, `whisper=false`, and one video.

3. commit and push directly to the request branch;
4. poll the new private batch receipt;
5. verify exactly-once batch accounting;
6. require proven transcript and comment coverage;
7. verify these paths:

```text
videos/JsrwIGbuM8o/snapshots/<SNAPSHOT_KEY>/
videos/JsrwIGbuM8o/pointers/latest.json
videos/JsrwIGbuM8o/pointers/best.json
videos/JsrwIGbuM8o/pointers/best-complete.json
memory/by-video-id/JsrwIGbuM8o.json
retention/manifest.json
```

8. confirm the memory pointer includes `preferred_result_path`, the selected request profile requests 100 comments, and the retention object includes refresh and delete-or-refresh deadlines;
9. confirm retrieved content is marked `EXTERNAL_UNTRUSTED_CONTENT`;
10. confirm the separate memory workflow is manual repair-only;
11. verify every required reader file is privately accessible;
12. report only evidence-backed `PROVEN`, `REJECTED`, `NOT_PROVEN`, or `BLOCKED` claims.

Do not publish generated research or logs to the public repository.

## Finish

After the test succeeds:

1. customize the persistent instruction from `GPT_MEMORY.md` with the user's actual private repository;
2. explain that normal research follows `preferred_result_path` while current statistics use `latest.json`;
3. tell the user that API retention deadlines are recorded but automated refresh/purge is not yet claimed;
4. point to:
   - `MEMORY_BANK.md`
   - `SNAPSHOT_STORAGE.md`
   - `YOUTUBE_DATA_RETENTION.md`
   - `BATCH_USAGE.md`.

Do not ask whether to continue. Continue until the manual secret step, a genuine hard blocker, or proven completion.
