# Install through ChatGPT and MagicMusic

Tell ChatGPT:

```text
Read organicoverlords/AITubeTranscript/MAGICMUSIC_INSTALL.md and follow it completely. Use my authenticated GitHub account and continue until the API-key step or installation is proven.
```

Use the exact runner prefix:

```text
# magicmusic-run
```

MagicMusic only runs the self-contained PowerShell payload. ChatGPT plans and validates.

## Target architecture

```text
public tool:             organicoverlords/AITubeTranscript
private repo:            <authenticated-user>/aitube-private
request branch/file:     request/aitube-live / aitube-requests/current.json
durable branch:          aitube-durable
volatile branch:         aitube-volatile
legacy branch:           aitube-results, migration/recovery only
memory contract version: 2026-08-05-v1
secret:                  YOUTUBE_API_KEY
```

## First payload

Use one self-contained PowerShell script to:

1. verify Windows, Git, GitHub CLI, authentication, and username;
2. create or prove a private repository outside the MagicMusic runner repo;
3. install the current pinned request, retention, migration, and request-JSON templates;
4. create and push `request/aitube-live`;
5. verify Actions write permissions and branch policies;
6. install or upgrade the public package;
7. verify these commands exist:

```text
aitube-transcript
aitube-batch
aitube-select-snapshot
aitube-check-memory-contract
aitube-verified-reader
aitube-retention-maintenance
aitube-legacy-split-migration
```

8. verify public workflow references use immutable SHAs;
9. prove the repository remains private;
10. print a compact receipt without credentials.

Fail closed on authentication, visibility, repository identity, dirty state, mutable references, stale templates, or branch-policy mismatch.

## Only manual step

Create a restricted YouTube Data API v3 key and save it in the private repository Actions secrets as:

```text
YOUTUBE_API_KEY
```

Never paste the key into chat or MagicMusic. Reply `secret added`.

## Verification after `secret added`

Use a second self-contained payload to:

1. verify repo identity, privacy, branches, pinned workflows, and secret-name existence;
2. submit a unique English/100-comments/non-Whisper request for `JsrwIGbuM8o`;
3. require proven durable transcript and exactly-once batch accounting;
4. require a current volatile overlay and sufficient comments when available;
5. require `aitube-select-snapshot` to return `SATISFIED`;
6. run:

```text
aitube-check-memory-contract ... --saved-contract-version 2026-08-05-v1
```

and require `MEMORY_CONTRACT_CURRENT`;

7. run `aitube-verified-reader` in `TRANSCRIPT_COMPLETE` mode and require:

```text
READING_COVERAGE=PROVEN
completed_video_count=selected_video_count
missing_video_ids=[]
```

8. verify `reading-pack.md`, `reading-ledger.json`, `access-receipt.json`, and `access-ledger.jsonl` were created in a private task output directory;
9. run volatile maintenance and require reachable-tree rewrite proof;
10. report physical host garbage collection as `NOT_INDEPENDENTLY_PROVEN`;
11. report only evidence-backed `PROVEN`, `REJECTED`, `NOT_PROVEN`, or `BLOCKED` claims.

## Existing repository upgrade

When `aitube-results` exists, run the one-time split migration. It must not refetch. Verify durable/volatile counts, conservative legacy inference, and that new work no longer writes to the legacy branch.

After migration, run the live contract checker and the verified reader smoke test.

## Backup policy

Back up `aitube-durable` only. Do not place `aitube-volatile` in indefinite immutable backups unless equivalent expiry controls exist.

## Finish

1. give the user the prefilled block from `GPT_MEMORY.md`;
2. explain exact-ID durable lookup, volatile discovery/API lookup, requirement selection, verified reading/access ledgers, retention, and physical-GC limits;
3. point to `MEMORY_BANK.md`, `VERIFIED_READER.md`, `READING_WORKFLOW.md`, `STORAGE_BOUNDARY.md`, and `YOUTUBE_DATA_RETENTION.md`.

Continue until the manual secret step, a genuine blocker, or proven completion.
