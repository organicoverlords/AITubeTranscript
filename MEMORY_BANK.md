# Permanent GitHub memory bank for ChatGPT

AITubeTranscript stores stable transcript evidence separately from time-limited YouTube API material. ChatGPT memory stores only stable paths, the memory-contract version, and operating rules.

```text
AITUBE_MEMORY_CONTRACT_VERSION=2026-08-05-v1
```

## Layers

```text
ChatGPT saved memory
  contract version, repositories, branches, lookup order, proof and reading rules

aitube-durable
  transcript chunks, manifests, receipts, hashes, exact video/batch pointers

aitube-volatile
  titles, descriptions, comments, API metadata, catalogs, retention indexes
```

`aitube-results` is migration or explicit legacy recovery only.

## Live contract check

Run `aitube-check-memory-contract` before substantial or multi-video work when saved routing may be stale. It validates both live bank manifests and compares the saved contract version.

A stale saved prompt must not override a valid live split layout.

## Lookup order

Known URL/ID:

1. extract the 11-character ID;
2. read `aitube-durable/memory/by-video-id/<VIDEO_ID>.json`;
3. inspect transcript proof and exact reader-manifest path;
4. use the volatile exact-ID overlay only when descriptions, comments, freshness, or API fields matter.

Unknown ID:

1. search `aitube-volatile/memory/video-index.jsonl`;
2. confirm title/channel/date/duration/ID;
3. follow the durable exact-ID pointer;
4. select evidence by explicit requirements.

## Selection

Use `aitube-select-snapshot`. Require `SATISFIED`; do not assume one universal latest or best pointer satisfies language, provider, comment count, or freshness requirements.

## Verified reading

Use `aitube-verified-reader` for one or many IDs or a stored batch. It produces:

```text
reading-pack.md
reading-ledger.json
access-receipt.json
access-ledger.jsonl
```

This provides one bounded document for an agent and a precise record of which files were actually opened for the current analysis.

`READING_COVERAGE=PROVEN` is file-coverage proof only. It does not prove transcript accuracy or interpretation quality.

## Reuse and refresh

A new chat is not a reason to refetch. Reuse proven durable transcripts whenever they satisfy the request. An expired volatile overlay does not invalidate transcript-only work.

Refresh when current API data is needed, requirements differ, proof is insufficient, or a required overlay is absent/expired.

## Proof

Transcript use requires proven status and coverage plus exactly-once ordered representation with no missing, duplicate, or unexpected indices.

Comments additionally require proven status/coverage, sufficient count, and non-expired retention.

Keep retrieval proof, reading proof, textual accuracy, API freshness, and synthesis quality as separate claims.

## Retention

Scheduled maintenance removes expired overlays from the reachable volatile tree and rewrites `aitube-volatile` as one parentless reachable commit. Physical GitHub garbage collection of unreachable objects is not independently proven.

Back up durable transcript evidence separately. Do not create indefinite immutable backups of volatile API data.

## Saved-memory boundary

Use `GPT_MEMORY.md`. Save stable paths and rules only. Never save credentials, transcripts, comments, descriptions, catalogs, access-ledger contents, temporary SHAs, workflow IDs, or transient errors.
