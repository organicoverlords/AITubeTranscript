# GPT memory instructions

Copy one block into ChatGPT and ask it to remember the instruction for future YouTube research requests.

## Prefilled instruction for `organicoverlords`

```text
For future YouTube research requests, use the optimized private AITubeTranscript workflow and its permanent GitHub memory bank.

Canonical locations:
- Public tool source: organicoverlords/AITubeTranscript
- Private execution, results, and memory repository: organicoverlords/all
- Preferred private request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Private results and memory branch: aitube-results
- Memory manifest: memory/bank-manifest.json
- Video index: memory/video-index.jsonl
- Known video lookup: memory/by-video-id/<VIDEO_ID>.json
- Channel index: memory/channel-index.jsonl
- Batch index: memory/batch-index.jsonl

Do not search for the repositories or reread setup documentation unless the fast path or memory lookup fails.

MEMORY-FIRST RULES

1. For a supplied YouTube URL, extract the 11-character video ID and first read memory/by-video-id/<VIDEO_ID>.json on aitube-results.
2. For a title, topic, channel, publication date, or vague reference to an earlier video, read the compact memory/video-index.jsonl before searching the repository or starting a new fetch.
3. For channel history, read memory/channel-index.jsonl. For playlists or prior multi-video runs, read memory/batch-index.jsonl.
4. Reuse a stored result when it contains the requested transcript, description, comments, language, and proof. Do not refetch merely because this is a new chat.
5. Refresh only when the user explicitly requests a fresh fetch, asks for current views/likes/comments/channel inventory, asks for new comments or a different language/count, or the stored proof/content is insufficient.
6. Treat views, likes, comment totals, comments, visibility, and channel inventories as snapshots tied to fetched_at. Transcripts and descriptions are usually stable source material.
7. Follow the stored receipt_path and reader_manifest_path. Read only the bounded files needed for the current question, but open every file in read_order before claiming “I read every word.”
8. Require transcript_status=PROVEN and transcript_coverage_status=PROVEN. When comments were requested, require comments_status=PROVEN and comments_coverage_status=PROVEN. Verify exactly_once=true, missing_indices=[], duplicate_indices=[], unexpected_indices=[], and ordered_contiguous=true in the coverage manifests.
9. Distinguish proven retrieval coverage from transcript textual accuracy. Third-party or automatic transcript accuracy remains NOT_PROVEN. Mention visible defects and verify important quotations against the original video.
10. Keep full transcripts, descriptions, comments, catalogs, receipts, and indexes in the private repository. Never store their full contents in ChatGPT memory.
11. Never request, reveal, commit, or remember API keys, cookies, tokens, temporary commit SHAs, workflow run IDs, or transient errors.
12. Use stable videos/<VIDEO_ID>/latest/ paths for automation. Use the logical YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory name for downloaded folders or archives.

FETCH RULES WHEN MEMORY CANNOT SATISFY THE REQUEST

The same private request file supports one video, video_urls, playlist_url(s), and channel_url(s). Use a unique request_id and commit directly to request/aitube-live. Default to languages=en, comments=100, whisper=false, and concurrency=4 unless the user requests otherwise.

For channel requests, default research_channel_videos=false so a channel URL creates a catalog without unexpectedly fetching every transcript. Set it true only when full research is requested, bounded by max_videos.

Poll the matching new receipt on aitube-results and confirm fetched_at or the blob SHA changed. Do not treat file existence or workflow success as proof.

For batches, require exactly-once accounting and distinguish a PROVEN accounting manifest from a PARTIAL result caused by deliberate playlist/channel limits, unavailable public metadata, or failed selected videos. Continue truncated sources with next_start_index.

Use the fast-cloud path first, the fallback ladder only when necessary, and Whisper only when captions cannot be retrieved. Avoid repository discovery, repeated README reads, full repository clones, full result.json retrieval, unrelated polling, rereading unchanged files, and temporary PRs when the direct request branch works.

The memory-bank contract is in organicoverlords/AITubeTranscript/MEMORY_BANK.md. The fetch contract is in GPT_FAST_PATH.md. Read them only when this saved instruction is missing, ambiguous, or a lookup/fetch fails.
```

## Generic instruction for another user

Replace the private repository placeholder before saving:

```text
For future YouTube research, use my private AITubeTranscript GitHub memory bank before starting a new fetch.

Canonical locations:
- Public tool: organicoverlords/AITubeTranscript
- Private repository: <OWNER>/<PRIVATE_REPOSITORY>
- Request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Results and memory branch: aitube-results
- Memory manifest: memory/bank-manifest.json
- Video index: memory/video-index.jsonl
- Video-ID lookup: memory/by-video-id/<VIDEO_ID>.json
- Channel index: memory/channel-index.jsonl
- Batch index: memory/batch-index.jsonl

Extract known video IDs and check their memory pointers first. For title, topic, channel, or date questions, inspect the compact indexes before repository search or a new fetch. Reuse stored proven material unless the user requests a refresh, current statistics, new comments, a different language/count, or missing proof/content. Follow the stored receipt and reader manifest, and only claim complete reading after every required reader file has been opened. Treat metadata and comments as fetched_at snapshots. Keep full research private and never store credentials or full transcripts in ChatGPT memory. Use MEMORY_BANK.md and GPT_FAST_PATH.md only when the saved path fails or needs repair.
```

## Store only stable workflow facts

Store:

- canonical repositories, branches, and lookup paths
- memory-first lookup and refresh rules
- supported request modes and safe defaults
- privacy requirements
- proof and complete-reading gates
- timing rules and fallback order
- batch and channel continuation behavior
- stable versus logical naming rules

Do not store:

- API keys, cookies, tokens, or authentication material
- one-time workflow run IDs or temporary commit SHAs
- video-specific transcripts, descriptions, comments, or catalogs
- transient errors or logs
