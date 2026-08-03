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

MagicMusic is only the local PowerShell runner. ChatGPT must plan, generate safe scripts, validate every result, and report proof. Do not delegate judgment to MagicMusic or give the user a long manual checklist.

## Target architecture

```text
public tool:             organicoverlords/AITubeTranscript
private repo:            <authenticated-user>/aitube-private
main branch:             main
request branch:          request/aitube-live
request file:            aitube-requests/current.json
durable evidence branch: aitube-durable
volatile API branch:     aitube-volatile
legacy branch:           aitube-results, migration only
secret:                  YOUTUBE_API_KEY
```

The installed system must support:

- one or many videos;
- playlists and channel catalogs;
- durable transcript-only snapshots;
- rewritable YouTube API overlays;
- requirement-based snapshot selection;
- scheduled retention evaluation and purge;
- exact transcript proof and reading manifests;
- one-time migration from the old mixed branch.

## First MagicMusic payload

Use one self-contained PowerShell payload to:

1. verify Windows, Git, GitHub CLI, `gh auth status`, and authenticated username;
2. work outside the MagicMusic runner repository;
3. create `<username>/aitube-private` when absent, or prove the existing repository is private;
4. clone and verify identity, remote, branch, HEAD, and clean working tree;
5. download the current public templates:
   - `templates/private-aitube-request.yml`
   - `templates/private-aitube-retention.yml`
   - `templates/private-aitube-migrate.yml`
   - `templates/aitube-request.json`
6. install them as:
   - `.github/workflows/private-aitube-request.yml`
   - `.github/workflows/private-aitube-retention.yml`
   - `.github/workflows/private-aitube-migrate.yml`
   - `aitube-requests/current.json`
7. verify all Actions, reusable workflows, and tool revisions use full immutable commit SHAs;
8. verify the request workflow calls the split durable/volatile `batch-fetch.yml`;
9. verify the retention workflow has a schedule and manual dispatch, calls `volatile-maintenance.yml`, and never uploads volatile API data as an artifact;
10. verify the migration workflow is manual-only and calls the legacy split migration command;
11. commit and push the files to `main`;
12. create and push `request/aitube-live` from that exact commit;
13. enable repository-content writes for Actions;
14. verify repository rules do not block trusted durable writes or required volatile force rewrites;
15. prove remotely that the repository remains private and both branches plus all files are correctly configured;
16. print a compact receipt without tokens or secrets.

Fail closed on authentication failure, public visibility, repository mismatch, dirty state, mutable workflow references, stale templates, unexpected existing files, or branch-policy mismatch.

## Only manual step

Open:

- Google Cloud Console to enable YouTube Data API v3 and create a restricted API key;
- `https://github.com/<authenticated-user>/aitube-private/settings/secrets/actions/new`.

Save the key as:

```text
YOUTUBE_API_KEY
```

Never ask the user to paste it into chat or MagicMusic. Pause and ask them to reply:

```text
secret added
```

## Verification after `secret added`

Use a second self-contained `# magicmusic-run` payload to:

1. re-verify repository identity, privacy, branches, pinned workflow references, and secret-name existence without reading the secret;
2. update `aitube-requests/current.json` on `request/aitube-live` with a unique request for:

```text
https://www.youtube.com/watch?v=JsrwIGbuM8o
```

Use English, 100 comments, `whisper=false`, and one video.

3. commit and push directly to the request branch;
4. poll the new durable batch receipt;
5. verify exactly-once batch accounting and proven transcript coverage;
6. verify on `aitube-durable`:

```text
videos/JsrwIGbuM8o/snapshots/<SNAPSHOT_KEY>/
videos/JsrwIGbuM8o/pointers/best-transcript.json
memory/by-video-id/JsrwIGbuM8o.json
batches/<REQUEST_ID>/latest/batch-receipt.json
```

7. prove the durable snapshot contains transcript chunks/manifests and excludes descriptions, comments, raw API results, statistics, and catalogs;
8. verify on `aitube-volatile`:

```text
videos/JsrwIGbuM8o/overlays/<SAME_SNAPSHOT_KEY>/
videos/JsrwIGbuM8o/pointers/latest.json
videos/JsrwIGbuM8o/pointers/best-comments.json
memory/by-video-id/JsrwIGbuM8o.json
retention/manifest.json
```

9. require proven comments, at least 100 retrieved comments when available, and a current retention state;
10. run requirement selection for English, minimum 100 comments, and maximum API age 25 days; require `selection_status=SATISFIED`;
11. confirm all retrieved content is marked `EXTERNAL_UNTRUSTED_CONTENT`;
12. run volatile maintenance manually once and require `VOLATILE_RETENTION_MAINTENANCE=PROVEN`;
13. confirm `aitube-volatile` was rewritten as one parentless reachable commit and no public or permanent artifact contains volatile data;
14. explicitly report physical host garbage collection as `NOT_INDEPENDENTLY_PROVEN`;
15. verify every durable reader file is privately accessible;
16. report only evidence-backed `PROVEN`, `REJECTED`, `NOT_PROVEN`, or `BLOCKED` claims.

## Existing repository upgrade

When `aitube-results` exists, run the manual migration workflow once after installing the new templates.

Verify it:

- migrates currently materialized transcript bundles to `aitube-durable`;
- migrates API-derived material to `aitube-volatile`;
- marks inferred legacy settings conservatively;
- preserves video, channel, and batch counts;
- does not refetch YouTube;
- does not claim recovery of variants available only in old Git history;
- stops new workflows from writing to `aitube-results`.

Keep the old branch only as an explicitly labeled legacy recovery source until the operator decides how to retire it. Branch deletion alone is not proof of physical data deletion.

## Backup policy

Configure durable backup for `aitube-durable` only.

Do not include `aitube-volatile` in an indefinite mirror, Git bundle, release asset, or immutable archive unless equivalent expiry controls exist.

## Finish

After proof:

1. customize the persistent instruction from `GPT_MEMORY.md` with the actual private repository;
2. explain that exact transcript lookup starts on `aitube-durable` while title discovery and API data use `aitube-volatile`;
3. explain requirement-based selection rather than universal best/latest assumptions;
4. explain scheduled purge and the physical-GC proof limitation;
5. point to:
   - `STORAGE_BOUNDARY.md`
   - `MEMORY_BANK.md`
   - `SNAPSHOT_STORAGE.md`
   - `YOUTUBE_DATA_RETENTION.md`
   - `BATCH_USAGE.md`
   - `READING_WORKFLOW.md`.

Do not ask whether to continue. Continue until the manual secret step, a genuine hard blocker, or proven completion.
