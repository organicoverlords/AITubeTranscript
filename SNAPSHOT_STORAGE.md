# Split snapshot storage

AITubeTranscript no longer stores durable transcript evidence and time-limited YouTube API data in one immutable bundle.

Read [`STORAGE_BOUNDARY.md`](STORAGE_BOUNDARY.md) first.

## Durable transcript snapshots

Branch:

```text
aitube-durable
```

Layout:

```text
videos/<VIDEO_ID>/
├── snapshots/
│   └── <UTC_TIMESTAMP_US>__<PROFILE_HASH_12>__<BUNDLE_HASH_12>/
├── pointers/
│   ├── latest.json
│   ├── best.json
│   └── best-transcript.json
└── latest/
```

A durable video snapshot contains only transcript evidence and internal proof:

```text
receipt.json
reader-manifest.json
transcript-manifest.json
transcript.md when available
chunks/*.md
snapshot-metadata.json
```

It excludes descriptions, comments, raw API metadata, channel catalogs, and statistics.

## Volatile API overlays

Branch:

```text
aitube-volatile
```

Layout:

```text
videos/<VIDEO_ID>/
├── overlays/<DURABLE_SNAPSHOT_KEY>/
├── pointers/
│   ├── latest.json
│   ├── best-comments.json
│   └── best-complete.json
└── current/
```

An overlay can contain:

```text
description.md
comments.md
comments-manifest.json
comment-chunks/
api-result.json
overlay-metadata.json
```

Channel catalogs are volatile-only and have `latest`, `widest-catalog`, and `freshest-complete` selectors.

## Request profiles and keys

Durable profiles record transcript-relevant settings:

```json
{
  "languages": "en",
  "whisper": false,
  "transcript_source": "provider:language"
}
```

Comment requirements belong to the API overlay rather than the durable transcript profile.

Snapshot keys include microseconds, the complete normalized profile hash, and the bundle hash prefix. A same-second fetch with different source content therefore creates a different immutable snapshot instead of colliding.

## Requirement-based selection

Do not treat a universal `best.json` pointer as sufficient for every request.

Use:

```bash
aitube-select-snapshot VIDEO_ID \
  --durable-root <DURABLE_CHECKOUT> \
  --volatile-root <VOLATILE_CHECKOUT> \
  --language en \
  --min-comments 100 \
  --max-api-age-days 25 \
  --prefer-source youtube-captions
```

Selection can require:

- proven transcript and transcript coverage;
- an exact language;
- a minimum retrieved comment count;
- an API overlay no older than a specified age;
- a preferred transcript source.

The selector returns exact durable and volatile paths plus reasons. It returns `UNSATISFIED` instead of silently weakening a requirement.

Convenience pointers remain useful:

```text
best-transcript.json  strongest convenient durable transcript pointer
best-comments.json    largest proven current overlay comment set
best-complete.json    convenient transcript-plus-comments overlay
latest.json           newest snapshot or overlay
```

`latest` never means strongest by definition.

## Publication model

Normal private publication is serialized under one concurrency lock:

1. fetch and prove the selected research;
2. publish transcript-only immutable snapshots to `aitube-durable`;
3. publish descriptions, comments, metadata, and catalogs to `aitube-volatile`;
4. verify forbidden API payloads do not exist in durable snapshots;
5. update durable and volatile indexes;
6. append a normal durable commit;
7. rewrite the volatile branch as one parentless reachable commit.

A real durable commit error fails publication. The workflow explicitly distinguishes `NO_CHANGES` from an actual commit failure.

## Integrity and trust

Every durable snapshot records:

- request-profile SHA-256;
- transcript bundle SHA-256;
- transcript proof fields;
- exact receipt and reader paths;
- the corresponding volatile overlay branch/path;
- `EXTERNAL_UNTRUSTED_CONTENT` classification.

Every volatile overlay records:

- API source and authorization classification;
- comment counts and proof where applicable;
- refresh and delete-or-refresh deadlines;
- its durable transcript reference;
- its overlay hash and untrusted-content classification.

## Legacy split migration

Older deployments used the mixed `aitube-results` branch. Migrate once with:

```text
aitube-legacy-split-migration
```

The migration processes currently materialized legacy `latest/` bundles without refetching. Inferred request settings are conservative and marked as legacy-derived. It does not recover richer variants that survive only in old Git history.

After proven migration, new requests must write only to `aitube-durable` and `aitube-volatile`. Keep `aitube-results` only as an explicitly labeled legacy recovery source until the operator decides how to retire it.
