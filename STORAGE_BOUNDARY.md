# Durable transcript evidence and volatile API overlays

AITubeTranscript separates stable transcript evidence from time-limited YouTube Data API material.

## Canonical private branches

```text
request branch:          request/aitube-live
durable evidence branch: aitube-durable
volatile API branch:     aitube-volatile
legacy mixed branch:     aitube-results
```

`aitube-results` is an upgrade source only after the split migration. New production fetches must not write to it.

## Durable branch

`aitube-durable` is append-oriented and keeps:

- transcript chunks and transcript manifests;
- transcript-only reader manifests;
- sanitized transcript receipts and coverage proof;
- request profiles and content hashes;
- durable batch accounting;
- exact video-ID and batch pointers.

It deliberately excludes:

```text
description.md
comments.md
comments-manifest.json
comment-chunks/
result.json
api-result.json
channel catalogs
view, like, and comment statistics
```

Canonical video layout:

```text
videos/<VIDEO_ID>/
├── snapshots/<TIMESTAMP_US>__<PROFILE_HASH>__<BUNDLE_HASH>/
├── pointers/
│   ├── latest.json
│   ├── best.json
│   └── best-transcript.json
└── latest/
```

The exact known-video lookup is:

```text
memory/by-video-id/<VIDEO_ID>.json
```

## Volatile branch

`aitube-volatile` contains YouTube Data API overlays:

- titles, channel information, descriptions, dates, durations, and statistics;
- top-level comments and comment manifests;
- playlists and channel-upload catalogs;
- API-backed batch references;
- retention deadlines and API-focused title/channel indexes.

Canonical video layout:

```text
videos/<VIDEO_ID>/
├── overlays/<DURABLE_SNAPSHOT_KEY>/
├── pointers/
│   ├── latest.json
│   ├── best-comments.json
│   └── best-complete.json
└── current/
```

Channel selectors include:

```text
latest.json
widest-catalog.json
freshest-complete.json
```

The volatile branch is rewritten after every publication or maintenance pass as a new parentless commit. Only one commit remains reachable from the branch. This prevents ordinary branch history from becoming a permanent API-data archive.

The workflow can prove the reachable branch tree was rewritten. It cannot independently prove when GitHub physically garbage-collects every unreachable object. The retention manifest therefore records:

```text
history_model = SINGLE_REACHABLE_COMMIT_REWRITE
physical_host_garbage_collection = NOT_INDEPENDENTLY_PROVEN
```

Do not create permanent mirrors, release assets, long-lived workflow artifacts, or immutable backups of the volatile branch.

## Composed research result

A normal video research result combines:

```text
durable transcript snapshot
+
optional unexpired API overlay
```

The durable pointer records the expected volatile overlay branch and path. Transcript-only work can continue after an API overlay expires. Questions needing descriptions, comments, current metadata, or channel inventory require a satisfactory unexpired overlay.

## Requirement-based selection

Use `aitube-select-snapshot` instead of assuming one universal `best` result:

```bash
aitube-select-snapshot VIDEO_ID \
  --durable-root <AITUBE_DURABLE_CHECKOUT> \
  --volatile-root <AITUBE_VOLATILE_CHECKOUT> \
  --language en \
  --min-comments 100 \
  --max-api-age-days 25
```

The selector checks:

- transcript and coverage proof;
- requested language;
- minimum comment count;
- API-overlay age and expiry;
- optional transcript-provider preference.

It returns `SATISFIED` with exact paths and reasons, or `UNSATISFIED` with per-snapshot rejection reasons.

## Snapshot keys

New durable snapshot keys use:

```text
<TIMESTAMP_WITH_MICROSECONDS>__<PROFILE_HASH_12>__<BUNDLE_HASH_12>
```

This avoids collisions between same-second fetches with the same request profile but different content.

## Retention maintenance

The scheduled private maintenance workflow:

1. checks every volatile overlay;
2. marks it `CURRENT`, `REFRESH_DUE`, or `EXPIRED`;
3. removes expired overlays from the reachable tree;
4. repairs current and preferred pointers;
5. rebuilds volatile indexes and the retention manifest;
6. rewrites `aitube-volatile` as one new parentless commit.

It does not automatically refetch every due overlay. A refresh requires a normal request when the material is still needed.

## Migration from `aitube-results`

Run the one-time split migration against the currently materialized legacy tree:

```bash
aitube-legacy-split-migration \
  --legacy-root <AITUBE_RESULTS_CHECKOUT> \
  --durable-root <AITUBE_DURABLE_CHECKOUT> \
  --volatile-root <AITUBE_VOLATILE_CHECKOUT>
```

The migration:

- copies transcript evidence into `aitube-durable`;
- copies API-derived fields into `aitube-volatile`;
- marks inferred legacy request settings conservatively;
- migrates currently materialized video, channel, and batch `latest/` bundles;
- does not refetch YouTube;
- does not claim recovery of variants that survive only in old Git commits.

## Branch protection and backup

Protect `aitube-durable` against force pushes and deletion. Permit only the trusted Actions writer and approved maintainers.

Do not apply no-force protection to `aitube-volatile`: lifecycle maintenance requires a force rewrite. Restrict who may update it instead.

Back up the durable branch independently. Exclude the volatile branch from permanent backups unless the backup system has matching expiry and deletion controls.
