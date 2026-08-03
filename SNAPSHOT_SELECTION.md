# Requirement-based snapshot selection

`best.json` is a convenient default, not proof that a snapshot satisfies a specific request.

Use the requirement-based selector when language, comments, transcript proof, source preference, or API freshness matter:

```bash
aitube-select-snapshot /path/to/private/vault VIDEO_ID \
  --language en \
  --min-comments 100 \
  --max-api-age-days 25 \
  --prefer-source youtube-captions
```

The selector reads immutable `snapshot-metadata.json` files and returns either:

```text
selection_status = SATISFIED
```

with exact snapshot, receipt, reader-manifest, request-profile, evidence, retention, score, and reasons; or:

```text
selection_status = UNSATISFIED
```

when no stored snapshot meets every requirement.

## Rules

- A newer ten-comment snapshot does not satisfy a one-hundred-comment request.
- Transcript requirements require both transcript and transcript-coverage status to be `PROVEN`.
- Comment requirements require both comment and comment-coverage status to be `PROVEN` and the actual retrieved count to meet the minimum.
- Requested language must match the stored request profile.
- Expired API-backed snapshots are rejected.
- `--max-api-age-days` applies an additional freshness bound.
- Source preferences affect ranking only after all hard requirements pass.

Do not claim that `best.json`, `latest.json`, or a memory pointer satisfies a request until its profile and evidence have been checked or the selector returns `SATISFIED`.

## Retention status

Recalculate retention states from current time with:

```bash
aitube-retention-status /path/to/private/vault
```

The evaluator updates records and `retention/manifest.json` with:

```text
CURRENT
REFRESH_DUE
PURGE_REQUIRED
```

Exit code `3` means at least one API-backed record requires purge or refresh action. This evaluator does not itself delete or refresh YouTube API data.
