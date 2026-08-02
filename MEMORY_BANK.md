# Permanent GitHub memory bank for ChatGPT

AITubeTranscript can use the private `aitube-results` branch as an external, durable memory bank. ChatGPT memory should retain only the stable repository pointers and retrieval rules. Full transcripts, descriptions, comments, receipts, and API credentials remain in the private GitHub repository.

## Why this design

ChatGPT memory is appropriate for small, stable instructions. It is not the right place for thousands of transcript segments or comments. GitHub provides durable storage, version history, exact files, hashes, and private access.

The split is:

```text
ChatGPT memory:
  repository + branch + lookup rules

Private GitHub memory bank:
  indexes + pointers + receipts + full source material
```

## Canonical private paths

```text
branch: aitube-results

memory/bank-manifest.json
memory/video-index.jsonl
memory/video-index.md
memory/channel-index.jsonl
memory/channel-index.md
memory/batch-index.jsonl
memory/batch-index.md
memory/by-video-id/<VIDEO_ID>.json
memory/by-title/<DATE>__<CHANNEL>__<TITLE>__<VIDEO_ID>.json
memory/by-channel-id/<CHANNEL_ID>.json
memory/by-batch-id/<BATCH_ID>.json
```

The complete source material stays at:

```text
videos/<VIDEO_ID>/latest/
channels/<CHANNEL_ID>/latest/
batches/<BATCH_ID>/latest/
```

## Stable names and logical download names

Automation must always use the stable video-ID path:

```text
videos/JsrwIGbuM8o/latest/
```

Each indexed video also receives:

```text
memory-entry.json
memory-entry.md
download-name.txt
```

The logical folder or archive name is:

```text
YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory
```

Example:

```text
2026-06-18__gamers-nexus__are-we-all-actually-f-d__JsrwIGbuM8o__aitube-memory
```

This makes downloaded folders understandable while preserving the exact YouTube ID needed for future retrieval.

## Retrieval rules for ChatGPT

### Known video URL or ID

1. Extract the 11-character video ID.
2. Read `memory/by-video-id/<VIDEO_ID>.json` from the private `aitube-results` branch.
3. When the pointer exists and required proof fields are acceptable, reuse the stored result.
4. Open its `receipt_path` and `reader_manifest_path`.
5. Read only the description, transcript chunks, or comment chunks required for the current question.

Do not fetch the video again merely because a new chat started.

### Known title, topic, channel, or date but no video ID

1. Read `memory/video-index.jsonl`.
2. Match title, channel, publication date, or other compact metadata.
3. Confirm the selected video by title, channel, date, duration, and ID.
4. Follow the stable result path from the entry.

For a human-readable overview, use `memory/video-index.md`. For exact machine retrieval, prefer JSONL.

### Channel questions

1. Read `memory/by-channel-id/<CHANNEL_ID>.json` when the ID is known.
2. Otherwise search `memory/channel-index.jsonl` by channel title.
3. Follow the catalog, Markdown, or JSONL path recorded by the entry.
4. Respect `status`, `catalog_exhausted`, and `next_start_index`; a deliberately limited catalog is `PARTIAL`, not complete.

### Playlist or batch questions

1. Read `memory/batch-index.jsonl` or `memory/by-batch-id/<BATCH_ID>.json`.
2. Open the referenced batch receipt.
3. Use its exact selected video IDs, failures, continuation offsets, and coverage evidence.

## Reuse versus refresh

Reuse the stored result when:

- the transcript coverage is `PROVEN`;
- the requested transcript, description, or stored comments are already present;
- the user asks about what the video said rather than current popularity statistics;
- no newer snapshot is explicitly required.

Refresh the video when:

- the user asks for current views, likes, comment count, or newly posted comments;
- the existing result lacks requested comments or language;
- proof fields are missing, rejected, or not applicable to required content;
- the user explicitly requests a fresh fetch;
- captions previously failed and a better fallback is now requested.

A transcript and description are normally stable source material. Views, likes, comment totals, comments, visibility, and channel inventories are time-dependent snapshots.

## Proof rules

Before claiming complete retrieval, require the same proof fields used by the normal fetch workflow:

```text
transcript_status = PROVEN
transcript_coverage_status = PROVEN
comments_status = PROVEN when comments were requested
comments_coverage_status = PROVEN when comments were requested
```

Verify the transcript and comment coverage manifests before claiming every retrieved item is represented exactly once.

Before claiming **“I read every word,”** open and consume every file listed by the result's `reader-manifest.json`.

The memory index proves where the material is stored. It does not prove the material was read in the current conversation.

## Source accuracy rules

Keep these claims separate:

- **Stored retrieval completeness:** can be `PROVEN` by manifests and hashes.
- **Transcript textual accuracy:** remains `NOT_PROVEN` for automatic captions and third-party transcript providers.
- **Current metadata accuracy:** valid only as of `fetched_at`.

Mention visible transcription defects. Verify important quotations against the original video before presenting them as exact.

## What ChatGPT should remember

Save this compact instruction as persistent memory:

```text
For future YouTube research, use my private AITubeTranscript GitHub memory bank before starting a new fetch.

Canonical locations:
- Public tool: organicoverlords/AITubeTranscript
- Private repository: organicoverlords/all
- Request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Results and memory branch: aitube-results
- Memory manifest: memory/bank-manifest.json
- Video index: memory/video-index.jsonl
- Video-ID lookup: memory/by-video-id/<VIDEO_ID>.json
- Channel index: memory/channel-index.jsonl
- Batch index: memory/batch-index.jsonl

Rules:
1. Extract a supplied YouTube video ID and check memory/by-video-id/<VIDEO_ID>.json first.
2. For title, channel, topic, or date queries, read the compact memory index before repository search or a new fetch.
3. Reuse a stored result when it contains the requested material with acceptable proof. Refresh only for missing content, failed proof, a requested language/comment change, current statistics, new comments, or an explicit fresh-fetch request.
4. Follow the stored receipt and reader-manifest paths. Read only the required bounded files, but open every reader file before claiming “I read every word.”
5. Treat views, likes, comments, and channel inventories as snapshots tied to fetched_at.
6. Distinguish proven retrieval coverage from unproven transcript textual accuracy.
7. Keep transcripts, descriptions, comments, receipts, and indexes in the private repository. Do not store their full content in ChatGPT memory.
8. Never store or request API keys, cookies, tokens, temporary workflow IDs, or temporary commit SHAs as memory.
9. Use stable video-ID paths for automation and the YYYY-MM-DD__channel__title__VIDEO_ID logical name for downloaded folders or archives.
10. Read organicoverlords/AITubeTranscript/MEMORY_BANK.md only when these rules are missing, ambiguous, or the memory-bank lookup fails.
```

Another user should replace `organicoverlords/all` with their own private companion repository.

## Installation

Copy:

```text
templates/private-aitube-memory-bank.yml
```

to the private repository as:

```text
.github/workflows/private-aitube-memory-bank.yml
```

It runs after the private fetch workflow and can also be started manually. It indexes all existing private results, so it serves as both an incremental update and a backfill operation.

The workflow never publishes the memory bank to the public source repository.
