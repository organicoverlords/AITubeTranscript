# GPT memory instructions

Copy one block into ChatGPT and ask it to remember the instruction for future YouTube research requests.

## Prefilled instruction for `organicoverlords`

```text
For future YouTube research requests, use the optimized private AITubeTranscript workflow.

Canonical locations:
- Public tool source: organicoverlords/AITubeTranscript
- Private execution and results repository: organicoverlords/all
- Preferred private request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Private results branch: aitube-results

Do not search for the repositories or reread setup documentation unless the fast path fails.

The same private request file supports one video, video_urls, playlist_url(s), and channel_url(s). Use a unique request_id and commit directly to request/aitube-live. Default to languages=en, comments=100, whisper=false, and concurrency=4 unless the user requests otherwise. Never exceed the documented limits.

For channel requests, generate a private catalog listing each selected public API-visible upload's title, exact publication timestamp/date, duration, video ID/URL, snapshot views/likes/comments, visibility, and live status. Default research_channel_videos=false so a channel URL lists the catalog without unexpectedly fetching every transcript. Set it true only when full transcript/description/comment research is requested, bounded by max_videos.

Poll the appropriate new result on aitube-results:
- videos/<video-id>/latest/receipt.json
- batches/<request-id>/latest/batch-receipt.json
- channels/<channel-id>/latest/channel-receipt.json

Confirm the timestamp or blob SHA changed so stale output is not mistaken for the new run.

For each selected video, require transcript_status=PROVEN and transcript_coverage_status=PROVEN. When comments were requested, require comments_status=PROVEN and comments_coverage_status=PROVEN. Verify transcript-manifest.json and comments-manifest.json: coverage.status=PROVEN, exactly_once=true, missing_indices=[], duplicate_indices=[], unexpected_indices=[], and ordered_contiguous=true.

For batches, require the batch receipt's accounting coverage to be PROVEN and exactly once. Distinguish a PROVEN accounting manifest from a PARTIAL source result caused by playlist/channel truncation, unavailable public metadata, or failed selected videos. Use next_start_index to continue truncated playlists or channel catalogs.

For channel catalogs, require channel-receipt coverage.status=PROVEN and report catalog_exhausted, truncated_by_limit, next_start_index, unavailable_video_count, and video_count. Only claim the full public catalog was listed when catalog_exhausted=true.

Read the applicable reader manifest, then actually open every required file. For videos, consume every description, transcript chunk, and comment chunk. For channel listings, consume channel-videos.md or every JSONL row. Only claim “I read every word” after every required reader file was opened.

Report request-to-fetch-complete, fetch-complete-to-reading-complete, and total request-to-reading-complete separately when timing is requested. For batches, also report requested, deduplicated, proven, partial, and failed counts, concurrency, truncation, and continuation offsets.

Distinguish retrieval completeness from transcript textual accuracy. Third-party or automatic transcript accuracy remains NOT_PROVEN. Mention visible defects and verify important quotations against the original video.

Keep all requests, workflow logs, transcripts, descriptions, comments, channel catalogs, and receipts private. Never publish them to organicoverlords/AITubeTranscript. Never request, reveal, commit, or store API keys, cookies, tokens, temporary commit SHAs, workflow run IDs, transcripts, comments, or transient errors as memory.

Use the fast-cloud path first, the fallback ladder only when necessary, and Whisper only when captions cannot be retrieved. Avoid repository discovery, repeated README reads, full repository clones, full result.json retrieval, unrelated polling, rereading unchanged files, and temporary PRs when the direct request branch works.

The full contract is in organicoverlords/AITubeTranscript/GPT_FAST_PATH.md. Read it only when this memory is missing, ambiguous, or the fast path fails.
```

## Generic instruction for another user

Replace the private repository placeholder before saving:

```text
For future YouTube research requests, use the optimized private AITubeTranscript workflow.

Canonical locations:
- Public tool source: organicoverlords/AITubeTranscript
- Private execution and results repository: <OWNER>/<PRIVATE_REPOSITORY>
- Preferred private request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Private results branch: aitube-results

Do not rediscover the repositories unless the fast path fails. The request file supports one video, many videos, playlists, and channel catalogs. Commit a unique private request, poll the matching private video/batch/channel receipt, verify exactly-once coverage, follow the reader manifests, and only then claim complete reading. Channel catalogs must include titles, publication dates/timestamps, durations, video IDs/URLs, and available snapshot statistics; only call a channel catalog complete when catalog_exhausted=true. Keep all generated research and credentials private. Use organicoverlords/AITubeTranscript/GPT_FAST_PATH.md only when the saved path fails or requires repair.
```

## Store only stable workflow facts

Store:

- canonical repositories, branches, and paths
- supported request modes and safe defaults
- privacy requirements
- proof and complete-reading gates
- timing rules and fallback order
- batch and channel continuation behavior

Do not store:

- API keys, cookies, tokens, or authentication material
- one-time workflow run IDs or temporary commit SHAs
- video-specific transcripts, descriptions, comments, or catalogs
- transient errors or logs
