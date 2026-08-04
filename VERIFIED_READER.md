# Verified one-command reading and live memory-contract checks

AITubeTranscript separates durable transcript evidence from retention-limited YouTube API overlays. Version `0.6.0` adds two commands that make this split easier and safer for ChatGPT and other agents.

## 1. Check the live memory contract

```bash
aitube-check-memory-contract \
  --durable-root <AITUBE_DURABLE_CHECKOUT> \
  --volatile-root <AITUBE_VOLATILE_CHECKOUT> \
  --saved-contract-version 2026-08-05-v1 \
  --output memory-contract-check.json
```

The command validates:

- `aitube-durable/memory/bank-manifest.json` exists and is schema 3.x or newer;
- `aitube-volatile/memory/bank-manifest.json` exists and is schema 3.x or newer;
- storage classes and cross-branch links are correct;
- saved GPT routing rules match `MEMORY_CONTRACT_VERSION=2026-08-05-v1`.

Statuses:

```text
MEMORY_CONTRACT_CURRENT
MEMORY_CONTRACT_STALE
MEMORY_CONTRACT_INVALID
```

A stale saved prompt must not force legacy routing. Use the live split layout, then update the saved memory prompt. `aitube-results` remains migration or explicit recovery only.

## 2. Select, open, hash, ledger, and materialize evidence

Known video IDs:

```bash
aitube-verified-reader HsJOQY1UN08 JsrwIGbuM8o \
  --durable-root <AITUBE_DURABLE_CHECKOUT> \
  --volatile-root <AITUBE_VOLATILE_CHECKOUT> \
  --output-dir <PRIVATE_TASK_OUTPUT>/youtube-reading \
  --mode TRANSCRIPT_COMPLETE \
  --language en \
  --purpose "3D texture pipeline research" \
  --saved-contract-version 2026-08-05-v1
```

Previously stored batch:

```bash
aitube-verified-reader \
  --batch-id <BATCH_ID> \
  --durable-root <AITUBE_DURABLE_CHECKOUT> \
  --volatile-root <AITUBE_VOLATILE_CHECKOUT> \
  --output-dir <PRIVATE_TASK_OUTPUT>/youtube-reading \
  --mode FULL_RESEARCH_COMPLETE \
  --language en \
  --min-comments 100 \
  --max-api-age-days 25 \
  --purpose "cross-video workflow comparison"
```

The command uses requirement-based snapshot selection, opens every manifest-selected file, hashes it, and writes:

```text
reading-pack.md
reading-ledger.json
access-receipt.json
access-ledger.jsonl
```

`reading-pack.md` combines the selected bounded files into one private agent-readable document. It does not include raw `result.json` or `api-result.json` when bounded transcript, description, and comment files suffice.

## Reading modes

```text
CATALOG_SCAN
TRANSCRIPT_COMPLETE
FULL_RESEARCH_COMPLETE
DEEP_SYNTHESIS
```

`DEEP_SYNTHESIS` prepares a fully verified source pack and records `PENDING_AGENT_SYNTHESIS`; the CLI does not claim that an external model understood or synthesized the material.

## Claim boundary

`READING_COVERAGE=PROVEN` means the command opened and hashed every manifest-selected file for the declared file mode. It does not prove:

- transcript textual accuracy;
- correctness of later interpretation;
- that a language model understood every word;
- freshness beyond the selected overlay's explicit retention state.

All retrieved transcripts, descriptions, and comments remain `EXTERNAL_UNTRUSTED_CONTENT`.

## Access ledger

Every run records:

- purpose;
- reading mode;
- selected video IDs and snapshot keys;
- expected and opened paths;
- byte counts and SHA-256 hashes;
- missing or expired evidence;
- completion status.

This distinguishes:

```text
stored in memory
```

from:

```text
opened for this particular analysis
```

Keep task access ledgers private. Do not place transcript or API payload contents in ChatGPT saved memory.
