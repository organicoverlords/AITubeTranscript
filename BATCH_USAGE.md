# Multiple videos, playlists, and channel catalogs

AITubeTranscript batches research data. It does **not** download or republish video or audio files.

Use the same private request file for every mode:

```text
aitube-requests/current.json
```

Commit the request to:

```text
request/aitube-live
```

The private fetch workflow writes results to `aitube-results`. The private memory workflow then indexes every successful video, channel catalog, and batch so future ChatGPT sessions can reuse them without refetching.

Before creating any request, GPT should check the private memory bank described in [`MEMORY_BANK.md`](MEMORY_BANK.md).

## Multiple videos

```json
{
  "request_id": "multi-20260803-001",
  "video_urls": [
    "https://www.youtube.com/watch?v=JsrwIGbuM8o",
    "https://www.youtube.com/watch?v=x8W_S9zmodk"
  ],
  "languages": "en",
  "comments": 100,
  "whisper": false,
  "max_videos": 100,
  "concurrency": 4
}
```

The workflow fetches up to six videos concurrently. The recommended default is four.

After indexing, each successful video has:

```text
memory/by-video-id/<VIDEO_ID>.json
videos/<VIDEO_ID>/latest/memory-entry.json
videos/<VIDEO_ID>/latest/download-name.txt
```

The stable video-ID path is used for automation. The logical download name is:

```text
YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory
```

## Playlist

```json
{
  "request_id": "playlist-20260803-001",
  "playlist_url": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
  "playlist_start_index": 0,
  "max_videos": 100,
  "languages": "en",
  "comments": 100,
  "whisper": false,
  "concurrency": 4
}
```

`max_videos` is the maximum number of full transcript/description/comment bundles in one run. The hard limit is 500.

When a playlist is larger than the selected limit, `batch-receipt.json` reports:

```text
playlist_catalog_status = PARTIAL
truncated_by_limit = true
next_start_index = <next zero-based offset>
```

Continue with a new request using that `next_start_index`. The batch memory entry preserves the selected videos, proof status, and continuation evidence:

```text
memory/by-batch-id/<REQUEST_ID>.json
```

## Several playlists and direct videos together

```json
{
  "request_id": "mixed-20260803-001",
  "video_urls": [
    "https://www.youtube.com/watch?v=JsrwIGbuM8o"
  ],
  "playlist_urls": [
    "https://www.youtube.com/playlist?list=FIRST_PLAYLIST_ID",
    "https://www.youtube.com/playlist?list=SECOND_PLAYLIST_ID"
  ],
  "max_videos": 200,
  "comments": 100,
  "concurrency": 4
}
```

Duplicate videos are removed before fetching. Their count is recorded in the batch receipt. Every successful unique video receives one stable memory pointer keyed by its YouTube ID.

## List a channel's videos

```json
{
  "request_id": "channel-catalog-20260803-001",
  "channel_url": "https://www.youtube.com/@CHANNEL_HANDLE",
  "channel_start_index": 0,
  "catalog_max_videos": 5000,
  "research_channel_videos": false
}
```

This creates a private channel catalog without fetching every transcript.

Each public API-visible upload records:

- channel upload index
- title
- video ID and URL
- exact publication timestamp
- publication date
- ISO 8601 duration
- duration in seconds
- readable duration such as `15:33` or `1:02:03`
- snapshot view, like, and comment counts
- privacy/API visibility status
- live-broadcast status

Results:

```text
channels/<channel-id>/latest/channel-receipt.json
channels/<channel-id>/latest/channel-videos.md
channels/<channel-id>/latest/channel-videos.jsonl
channels/<channel-id>/latest/channel-catalog.json
memory/by-channel-id/<channel-id>.json
```

The Markdown file is for humans. JSONL is the compact machine-readable list. The full JSON file includes channel details and proof fields. The memory pointer records the stable catalog paths, fetch timestamp, selected date range, exhaustion state, and continuation offset.

Supported channel references:

- raw `UC...` channel ID
- `@handle`
- `youtube.com/@handle`
- `youtube.com/channel/UC...`
- `youtube.com/user/...`

Ambiguous old `/c/...` URLs are rejected. Use the channel's current `@handle` or canonical `UC...` URL.

The default catalog limit is 5,000 public uploads and the hard limit is 20,000 per request. When a larger catalog is truncated, use `next_start_index` in the next request.

## Catalog a channel and research selected uploads

```json
{
  "request_id": "channel-research-20260803-001",
  "channel_url": "https://www.youtube.com/@CHANNEL_HANDLE",
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

This always creates the channel catalog, then fetches full research bundles for up to `max_videos` selected uploads. The channel and each successful researched video are indexed separately.

## Several channels

Use `channel_urls`:

```json
{
  "request_id": "channels-20260803-001",
  "channel_urls": [
    "https://www.youtube.com/@FIRST_HANDLE",
    "https://www.youtube.com/@SECOND_HANDLE"
  ],
  "catalog_max_videos": 5000,
  "research_channel_videos": false
}
```

## Batch proof and permanent lookup

Every run creates:

```text
batches/<request-id>/latest/batch-receipt.json
batches/<request-id>/latest/batch-reader-manifest.json
```

The receipt records:

- selected and deduplicated video IDs
- playlist expansion status and continuation offset
- channel catalog status and continuation offset
- success, partial, and failure counts
- one result entry for every selected video
- exactly-once batch accounting

The memory workflow adds:

```text
memory/batch-index.jsonl
memory/batch-index.md
memory/by-batch-id/<REQUEST_ID>.json
```

A batch can be `PARTIAL` even when its accounting is `PROVEN`. For example, this happens when a playlist or channel is intentionally truncated, a private/deleted channel upload has no public details, or one selected transcript cannot be retrieved.

## Memory reuse rules

Do not rerun a video simply because a new chat started. Reuse the indexed result when the requested transcript, description, language, comments, and proof are already present.

Refresh when the user requests:

- current views, likes, comment totals, or channel inventory
- newly posted comments
- a different transcript language or comment limit
- missing content or stronger fallback retrieval
- an explicit fresh snapshot

Views, likes, comments, visibility, and channel inventories are snapshots tied to `fetched_at`. See [`MEMORY_BANK.md`](MEMORY_BANK.md) for the full rule set.

## Limits

```text
Full research bundles per request: 500 maximum
Channel catalog rows per request: 20,000 maximum
Concurrent video fetches: 6 maximum
Recommended concurrency: 4
```

Use lower concurrency when Whisper is enabled. Whisper runs force concurrency to one.
