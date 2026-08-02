# GPT fast path for private YouTube research

This is the canonical operating contract for GPT or another agent with GitHub access.

## Canonical repositories for this deployment

- Public tool source: `organicoverlords/AITubeTranscript`
- Private execution, results, and memory repository: `organicoverlords/all`
- Private request branch: `request/aitube-live`
- Request file: `aitube-requests/current.json`
- Private results and memory branch: `aitube-results`
- Memory manifest: `memory/bank-manifest.json`
- Video index: `memory/video-index.jsonl`
- Video-ID pointers: `memory/by-video-id/<VIDEO_ID>.json`
- Channel index: `memory/channel-index.jsonl`
- Batch index: `memory/batch-index.jsonl`

Do not search for these repositories or reread setup documentation unless the saved paths fail.

## Step zero: consult permanent memory

A new chat is not a reason to refetch a video.

### Known video URL or ID

1. Extract the 11-character YouTube video ID.
2. Read `memory/by-video-id/<VIDEO_ID>.json` on `aitube-results`.
3. Confirm its title, channel, publication date, duration, `fetched_at`, requested content statuses, and proof statuses.
4. Follow its `receipt_path` and `reader_manifest_path`.
5. Reuse the stored result when it satisfies the request.

### Title, topic, channel, date, or vague reference to an earlier fetch

1. Read `memory/video-index.jsonl`.
2. Match the compact title, channel, publication date, duration, and video ID fields.
3. Confirm the chosen entry rather than guessing between similar titles.
4. Follow the stable video-ID result path.

For channel history use `memory/channel-index.jsonl`. For prior playlist or multi-video runs use `memory/batch-index.jsonl`.

### Reuse-versus-refresh decision

Reuse stored material when:

- the requested transcript, description, comments, or catalog are already present;
- required coverage is proven;
- the user asks what the video said rather than for current popularity or inventory;
- no newer snapshot is explicitly requested.

Start a fresh fetch when:

- the user explicitly asks to refresh;
- current views, likes, comment totals, new comments, visibility, or channel inventory are required;
- the stored result lacks the requested language, comment count, or source material;
- required proof is absent or rejected;
- a previous retrieval failed and another fallback is requested.

Views, likes, comments, visibility, and channel inventories are snapshots tied to `fetched_at`. Transcripts and descriptions are normally stable source material.

The memory index proves where data is stored. It does not prove that GPT read it in the current conversation.

## Fresh request path

Use this section only when permanent memory cannot satisfy the request.

1. Determine the request mode: one video, several videos, playlist(s), channel catalog(s), or a mixture.
2. Read `aitube-requests/current.json` from `organicoverlords/all` on `request/aitube-live` and retain its current blob SHA.
3. Replace the file on the same branch with a unique `request_id` and the appropriate fields below.
4. Commit directly to `request/aitube-live`. Do not create a temporary pull request unless this trigger fails.
5. Poll the new private receipt on `aitube-results`. Compare its timestamp or blob SHA with the prior result so stale output is never mistaken for the new request.
6. Inspect workflow runs or logs only when the expected receipt does not update within a reasonable interval.
7. After the fetch, confirm the private memory workflow updated the relevant memory pointer and compact indexes.

Fallback trigger order:

1. direct update of `request/aitube-live`
2. direct update of `main/aitube-requests/current.json`
3. same-repository request pull request
4. manual workflow dispatch

## Request formats

### One video

```json
{
  "request_id": "unique-id",
  "video_url": "full YouTube URL",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

### Several videos

```json
{
  "request_id": "unique-batch-id",
  "video_urls": [
    "first YouTube URL",
    "second YouTube URL"
  ],
  "languages": "en",
  "comments": 100,
  "whisper": false,
  "max_videos": 100,
  "concurrency": 4
}
```

### Playlist

```json
{
  "request_id": "unique-playlist-id",
  "playlist_url": "full playlist URL",
  "playlist_start_index": 0,
  "max_videos": 100,
  "languages": "en",
  "comments": 100,
  "whisper": false,
  "concurrency": 4
}
```

### Channel catalog only

```json
{
  "request_id": "unique-channel-id",
  "channel_url": "YouTube @handle or canonical channel URL",
  "channel_start_index": 0,
  "catalog_max_videos": 5000,
  "research_channel_videos": false
}
```

### Channel catalog plus full research for selected uploads

```json
{
  "request_id": "unique-channel-research-id",
  "channel_url": "YouTube @handle or canonical channel URL",
  "channel_start_index": 0,
  "catalog_max_videos": 5000,
  "research_channel_videos": true,
  "max_videos": 50,
  "languages": "en",
  "comments": 100,
  "whisper": false,
  "concurrency": 4
}
```

Plural fields are supported: `video_urls`, `playlist_urls`, and `channel_urls`. They may be mixed in one request. Duplicate video IDs are removed before fetching.

Use the requested language or comment count when specified. Leave `whisper` false unless captions cannot be retrieved. Whisper forces concurrency to one.

## Result and memory paths

### Individual video

```text
videos/<video-id>/latest/receipt.json
videos/<video-id>/latest/reader-manifest.json
videos/<video-id>/latest/memory-entry.json
videos/<video-id>/latest/download-name.txt
memory/by-video-id/<video-id>.json
```

Stable automation uses `videos/<video-id>/latest/`. Human downloads use the logical name recorded by `download-name.txt`:

```text
YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory
```

### Batch

```text
batches/<request-id>/latest/batch-receipt.json
batches/<request-id>/latest/batch-reader-manifest.json
memory/by-batch-id/<request-id>.json
```

### Channel catalog

```text
channels/<channel-id>/latest/channel-receipt.json
channels/<channel-id>/latest/channel-videos.md
channels/<channel-id>/latest/channel-videos.jsonl
channels/<channel-id>/latest/channel-catalog.json
memory/by-channel-id/<channel-id>.json
```

Channel rows include title, exact publication timestamp, publication date, ISO duration, duration seconds, readable duration, video URL, snapshot views/likes/comments, public API visibility, and live status.

## Individual-video completeness gates

File existence, a memory pointer, and workflow success do not prove completeness.

Require from `receipt.json`:

- `transcript_status = PROVEN`
- `transcript_coverage_status = PROVEN`
- `comments_status = PROVEN` when comments were requested
- `comments_coverage_status = PROVEN` when comments were requested

Read `transcript-manifest.json` and require:

- `coverage.status = PROVEN`
- `coverage.exactly_once = true`
- `coverage.missing_indices = []`
- `coverage.duplicate_indices = []`
- `coverage.unexpected_indices = []`
- `coverage.ordered_contiguous = true`

Read `comments-manifest.json` and require the equivalent fields when comments were requested.

## Batch completeness gates

Read `batch-receipt.json` and require its accounting coverage to show:

- `coverage.status = PROVEN`
- `coverage.exactly_once = true`
- `coverage.missing_indices = []`
- `coverage.duplicate_indices = []`
- `coverage.unexpected_indices = []`
- `coverage.ordered_contiguous = true`

Distinguish accounting from source completeness:

- `status = PROVEN` means every selected research bundle passed and all playlist/channel selections were exhausted.
- `status = PARTIAL` can still have proven accounting; a source may be deliberately truncated, public details may be unavailable, or a selected video may not pass every content gate.
- Use `next_start_index` to continue a truncated playlist or channel catalog.

Read `batch-reader-manifest.json`, then follow every entry in `private_read_order`.

## Channel catalog completeness gates

Read `channel-receipt.json` and require proven, exactly-once coverage with no missing, duplicate, or unexpected indices and ordered contiguous rows.

Also report:

- `status`
- `video_count`
- `catalog_exhausted`
- `truncated_by_limit`
- `next_start_index`
- `unavailable_video_count`

Only say the full public catalog was listed when `catalog_exhausted = true`. Private, deleted, members-only, region-blocked, or otherwise API-invisible videos may not expose complete public metadata.

## Complete reading contract

For every selected video:

1. Read the stored or newly generated `reader-manifest.json` first.
2. Open and consume every file listed in `read_order` when complete reading is requested.
3. Use `parallel_read_groups` when supported.
4. Do not retrieve large `result.json` unless a required field is unavailable elsewhere.
5. Do not reread unchanged files whose hashes were already fully returned and verified in this conversation.
6. Only claim **“I read every word”** after every required description, transcript chunk, and comment chunk has actually been opened and consumed.

For a focused question, read only the relevant bounded files and state that the answer is based on those files rather than claiming the entire bundle was consumed.

For a channel-listing request, read `channel-videos.md` or every JSONL row. Do not claim every channel video was listed unless the channel receipt proves the catalog was exhausted.

## Timing contract

For a new fetch record separately:

- request-to-fetch-complete
- fetch-complete-to-reading-complete
- total request-to-reading-complete

For a memory reuse, report memory-lookup-to-reading-complete when timing is requested; do not pretend a new YouTube fetch occurred.

For batches, also report video count, channel count, concurrency, and total batch duration. Use the user-message timestamp as the start only when its precision is known. Prefer an exact timestamp captured immediately before updating the request file or beginning the memory lookup.

## Required reports

### Video research

Report:

- whether the result was reused from memory or freshly fetched
- title, channel, publication date, and duration
- snapshot date for time-dependent metadata
- snapshot views, likes, and total comment count when available
- retrieved transcript segment count
- retrieved comment count
- transcript and comment coverage evidence
- concise summary
- dominant themes across fetched comments when relevant
- timing measurements when requested

### Playlist or multi-video research

Report requested, deduplicated, proven, partial, and failed counts; each selected video's status; truncation and continuation offsets; accounting evidence; and aggregate timing.

### Channel catalog

Report channel title and ID, reported and selected counts, exhaustion status, continuation offset, unavailable rows, requested per-upload fields, and catalog coverage evidence.

Distinguish:

- **Retrieval completeness:** may be `PROVEN` by receipts and manifests.
- **Transcript textual accuracy:** remains `NOT_PROVEN` when sourced from automatic captions or a third-party provider.
- **Current metadata accuracy:** valid only as of `fetched_at`.

Mention visible transcription defects. Verify important quotations against the original video before treating them as exact.

## Failure and privacy rules

- Use memory first.
- Use the fast-cloud fetch path when a refresh is required.
- Use the fallback ladder only when the fast path fails.
- Enable Whisper only when captions cannot be retrieved.
- Never publish requests, transcripts, descriptions, comments, catalogs, receipts, memory indexes, or workflow logs to the public source repository.
- Keep all generated research and indexes in the private repository.
- Never print, commit, request, or remember `YOUTUBE_API_KEY`, cookies, tokens, or credentials.
- Do not store full source material in ChatGPT memory.
- This tool collects research metadata and text; it does not download or redistribute video/audio media.

## Speed rules

Avoid:

- repository discovery
- repeated README inspection
- fetching a video already present with acceptable proof
- full private-repository clones
- full-history fetches
- unnecessary `result.json` reads
- sequential polling of unrelated workflow data
- rereading unchanged content
- temporary pull requests when the direct request branch works

Prefer direct memory pointers, compact JSONL indexes, bounded reader chunks, and four concurrent video fetches when a new batch is genuinely required. The supported maximum is six.
