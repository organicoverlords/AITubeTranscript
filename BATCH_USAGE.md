# Multiple videos, playlists, and channel catalogs

AITubeTranscript batches private research text and metadata. It does **not** download or redistribute video or audio media.

Use:

```text
request branch: request/aitube-live
request file:   aitube-requests/current.json
```

New publication writes transcript evidence to `aitube-durable` and API-derived material to `aitube-volatile`. It no longer writes new results to the legacy mixed `aitube-results` branch.

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

Maximum concurrency is six; recommended default is four.

Each successful video receives:

```text
aitube-durable:
  videos/<VIDEO_ID>/snapshots/<SNAPSHOT_KEY>/
  videos/<VIDEO_ID>/pointers/best-transcript.json
  memory/by-video-id/<VIDEO_ID>.json

aitube-volatile:
  videos/<VIDEO_ID>/overlays/<SNAPSHOT_KEY>/
  videos/<VIDEO_ID>/pointers/latest.json
  videos/<VIDEO_ID>/pointers/best-comments.json
  memory/by-video-id/<VIDEO_ID>.json
```

The same snapshot key links the durable transcript to its API overlay.

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

`max_videos` limits full selected-video research. The hard limit is 500.

When truncated, the source-expansion receipt reports:

```text
playlist_catalog_status = PARTIAL
truncated_by_limit = true
next_start_index = <next zero-based offset>
```

Continue with a new request using that offset.

## Mixed videos and playlists

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

Duplicate video IDs are removed and accounted for before research.

## List a channel's uploads

```json
{
  "request_id": "channel-catalog-20260803-001",
  "channel_url": "https://www.youtube.com/@CHANNEL_HANDLE",
  "channel_start_index": 0,
  "catalog_max_videos": 5000,
  "research_channel_videos": false
}
```

A channel catalog is YouTube API data and therefore lives only on `aitube-volatile`:

```text
channels/<CHANNEL_ID>/overlays/<SNAPSHOT_KEY>/
channels/<CHANNEL_ID>/current/
channels/<CHANNEL_ID>/pointers/latest.json
channels/<CHANNEL_ID>/pointers/widest-catalog.json
channels/<CHANNEL_ID>/pointers/freshest-complete.json
memory/by-channel-id/<CHANNEL_ID>.json
```

Each selected public API-visible upload can record title, video ID/URL, publication timestamp/date, duration, available statistics, visibility, and live status.

Supported channel references:

```text
UC... channel ID
@handle
youtube.com/@handle
youtube.com/channel/UC...
youtube.com/user/...
```

Ambiguous old `/c/...` URLs are rejected. Use a current handle or canonical channel ID.

Default catalog limit is 5,000 rows; hard limit is 20,000. Continue a truncated catalog with `next_start_index`.

## Catalog plus selected transcript research

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

This creates a volatile channel catalog plus durable transcript snapshots and optional volatile video overlays for up to `max_videos` selected uploads. Use `channel_urls` for several channels.

## Batch proof

Every batch receives durable internal accounting:

```text
aitube-durable:
  batches/<REQUEST_ID>/snapshots/<SNAPSHOT_KEY>/batch-receipt.json
  batches/<REQUEST_ID>/latest/batch-receipt.json
  memory/by-batch-id/<REQUEST_ID>.json
```

API-oriented batch references can also exist on `aitube-volatile`.

The durable receipt records selected video IDs, batch status, request hash, and exactly-once accounting. A batch may be `PARTIAL` while accounting remains `PROVEN` because a source was deliberately limited, metadata was unavailable, or a selected video failed.

## Select the correct result after a batch

A later request may use another language, fewer comments, or newer API data. Do not blindly use `latest`.

For each video, run requirement-based selection:

```bash
aitube-select-snapshot VIDEO_ID \
  --durable-root <DURABLE_CHECKOUT> \
  --volatile-root <VOLATILE_CHECKOUT> \
  --language en \
  --min-comments 100 \
  --max-api-age-days 25
```

The selector must return `SATISFIED`. It returns exact durable and overlay paths and explains why they match.

Convenience pointers:

```text
best-transcript.json  transcript evidence
best-comments.json    largest proven non-expired comment overlay
best-complete.json    convenient transcript/comment pairing
latest.json           newest item, not necessarily strongest
```

## Reading a fetched batch

Fetching is not reading.

Declare one mode:

```text
CATALOG_SCAN
TRANSCRIPT_COMPLETE
FULL_RESEARCH_COMPLETE
DEEP_SYNTHESIS
```

For `TRANSCRIPT_COMPLETE`:

1. open the durable batch receipt and require exactly-once accounting;
2. resolve each video through the durable exact-ID pointer;
3. select the correct durable snapshot;
4. open every durable reader manifest;
5. build a per-video ledger;
6. open every listed transcript chunk;
7. reconcile expected and opened files for every video.

For `FULL_RESEARCH_COMPLETE`, also resolve a satisfactory unexpired overlay and open each applicable description and requested comment file.

Process large batches in bounded groups, normally four or five videos at a time. A receipt, title list, segment count, reader manifest, or summary does not prove transcripts were read.

Report fetch, selection, transcript reading, full-research reading, synthesis, and total time separately. Label estimates.

See [`READING_WORKFLOW.md`](READING_WORKFLOW.md).

## Retention

`aitube-volatile` records API deadlines and dynamic state. Scheduled maintenance:

- marks records `CURRENT`, `REFRESH_DUE`, or `EXPIRED`;
- purges expired overlays from the reachable tree;
- repairs pointers and indexes;
- rewrites the volatile branch as one parentless reachable commit.

Maintenance does not automatically refresh every due record. Refresh still-needed API data through a new request.

Do not place the volatile branch in an indefinite immutable backup.

## Migration

Older installations use `aitube-results`. Run the one-time split migration to copy currently materialized transcript evidence to `aitube-durable` and API-derived material to `aitube-volatile` without refetching. It does not recover variants available only in old Git history.

## Limits

```text
Full selected-video research per request: 500
Channel catalog rows per request:       20,000
Concurrent video fetches:               6
Recommended concurrency:                4
```

Whisper forces concurrency one.

See:

- [`STORAGE_BOUNDARY.md`](STORAGE_BOUNDARY.md)
- [`SNAPSHOT_STORAGE.md`](SNAPSHOT_STORAGE.md)
- [`YOUTUBE_DATA_RETENTION.md`](YOUTUBE_DATA_RETENTION.md)
- [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md)
- [`READING_WORKFLOW.md`](READING_WORKFLOW.md)
