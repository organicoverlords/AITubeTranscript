# GPT fast path for private YouTube research

This is the canonical operating contract for GPT or another agent with GitHub access.

## Canonical repositories for this deployment

- Public tool source: `organicoverlords/AITubeTranscript`
- Private execution and results repository: `organicoverlords/all`
- Private request branch: `request/aitube-live`
- Request file: `aitube-requests/current.json`
- Private results branch: `aitube-results`

Do not search for these repositories or reread setup documentation unless the fast path fails.

## Fast request path

1. Determine the request mode: one video, several videos, playlist(s), channel catalog(s), or a mixture.
2. Read `aitube-requests/current.json` from `organicoverlords/all` on `request/aitube-live` and retain its current blob SHA.
3. Replace the file on the same branch with a unique `request_id` and the appropriate fields below.
4. Commit directly to `request/aitube-live`. Do not create a temporary pull request unless this trigger fails.
5. Poll the new private receipt on `aitube-results`. Compare its timestamp or blob SHA with the prior result so stale output is never mistaken for the new request.
6. Inspect workflow runs or logs only when the expected receipt does not update within a reasonable interval.

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

## Result paths

### Individual video

```text
videos/<video-id>/latest/receipt.json
```

### Batch

```text
batches/<request-id>/latest/batch-receipt.json
batches/<request-id>/latest/batch-reader-manifest.json
```

### Channel catalog

```text
channels/<channel-id>/latest/channel-receipt.json
channels/<channel-id>/latest/channel-videos.md
channels/<channel-id>/latest/channel-videos.jsonl
channels/<channel-id>/latest/channel-catalog.json
```

Channel rows include title, exact publication timestamp, publication date, ISO duration, duration seconds, readable duration, video URL, snapshot views/likes/comments, public API visibility, and live status.

## Individual-video completeness gates

File existence and workflow success do not prove completeness.

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
- `status = PARTIAL` can still have `coverage.status = PROVEN`; this means every selected item was accounted for, but a playlist/channel was truncated, a public detail was unavailable, or a selected video did not pass all content gates.
- Use `next_start_index` to continue a truncated playlist or channel catalog.

Read `batch-reader-manifest.json`, then follow every entry in `private_read_order`.

## Channel catalog completeness gates

Read `channel-receipt.json` and require:

- `coverage.status = PROVEN`
- `coverage.exactly_once = true`
- `coverage.missing_indices = []`
- `coverage.duplicate_indices = []`
- `coverage.unexpected_indices = []`
- `coverage.ordered_contiguous = true`

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

1. Read `reader-manifest.json` first.
2. Open and consume every file listed in `read_order`.
3. Use `parallel_read_groups` when supported.
4. Do not retrieve large `result.json` unless a field is unavailable elsewhere.
5. Do not reread unchanged files whose hashes were already verified.
6. Only claim **“I read every word”** after every required description, transcript chunk, and comment chunk has actually been opened and consumed.

For a channel-listing request, read `channel-videos.md` or every JSONL row. Do not claim every channel video was listed unless the channel receipt proves the catalog was exhausted.

## Timing contract

Record separately:

- request-to-fetch-complete
- fetch-complete-to-reading-complete
- total request-to-reading-complete

For batches, also report video count, channel count, concurrency, and total batch duration. Use the user-message timestamp as the start only when its precision is known. Prefer an exact timestamp captured immediately before updating the request file.

## Required reports

### Video research

Report:

- title, channel, publication date, and duration
- snapshot views, likes, and total comment count when available
- retrieved transcript segment count
- retrieved comment count
- description size
- transcript and comment coverage evidence
- concise summary
- dominant themes across fetched comments
- timing measurements

### Playlist or multi-video research

Report:

- requested, deduplicated, proven, partial, and failed counts
- each selected video's status
- playlist truncation and continuation offset
- batch accounting evidence
- aggregate timing

### Channel catalog

Report:

- channel title and ID
- reported and selected video counts
- whether the public uploads catalog was exhausted
- continuation offset when truncated
- unavailable row count
- for each selected upload: title, publication date, duration, video ID/URL, and requested snapshot statistics
- catalog coverage evidence

Distinguish:

- **Retrieval completeness:** may be `PROVEN` by receipts and manifests.
- **Transcript textual accuracy:** remains `NOT_PROVEN` when sourced from automatic captions or a third-party provider.

Mention visible transcription defects. Verify important quotations against the original video before treating them as exact.

## Failure and privacy rules

- Use the fast-cloud path first.
- Use the fallback ladder only when the fast path fails.
- Enable Whisper only when captions cannot be retrieved.
- Never publish requests, transcripts, descriptions, comments, catalogs, receipts, or workflow logs to the public source repository.
- Keep all generated research in the private repository.
- Never print or commit `YOUTUBE_API_KEY`, cookies, or credentials.
- This tool collects research metadata and text; it does not download or redistribute video/audio media.

## Speed rules

Avoid:

- repository discovery
- repeated README inspection
- full private-repository clones
- full-history fetches
- unnecessary `result.json` reads
- sequential polling of unrelated workflow data
- rereading unchanged content
- temporary pull requests when the direct request branch works

Prefer four concurrent video fetches. The supported maximum is six.
