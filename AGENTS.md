# Agent instructions

For YouTube research execution, do not infer the workflow from source files and do not rediscover repositories.

1. Read [`MEMORY_BANK.md`](MEMORY_BANK.md) first for the permanent private GitHub memory lookup, reuse-versus-refresh rules, logical naming, and proof requirements.
2. Read [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) when a new fetch is required.
3. Read [`BATCH_USAGE.md`](BATCH_USAGE.md) for request examples and limits.
4. Use [`GPT_MEMORY.md`](GPT_MEMORY.md) when the user asks what persistent instruction to save in ChatGPT.
5. Use [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md) for the streamlined ChatGPT installer.
6. Use [`INSTALL.md`](INSTALL.md) for manual private companion-repository setup.

Core invariants:

- Check `memory/by-video-id/<VIDEO_ID>.json` before fetching a known video again.
- Use compact memory indexes for title, channel, topic, date, playlist, and batch lookups.
- Reuse proven stored material unless freshness, missing content, changed parameters, or an explicit refresh requires a new fetch.
- Stable machine paths use video IDs; logical download names use `YYYY-MM-DD__channel__title__VIDEO_ID__aitube-memory`.
- Official GitHub execution and memory indexing must occur in a private repository.
- Generated requests, logs, transcripts, descriptions, comments, catalogs, memory indexes, manifests, and receipts remain private.
- The tool collects research text and metadata; it does not download or redistribute video/audio media.
- File existence, memory-index presence, and workflow success are not completeness proof.
- Verify video, batch, playlist-expansion, and channel-catalog coverage independently.
- Open every file required by the applicable reader manifest before claiming complete reading.
- Only call a channel catalog complete when `catalog_exhausted = true`.
- Treat views, likes, comments, visibility, and channel inventories as snapshots tied to `fetched_at`.
- Do not store full transcripts or credentials in ChatGPT memory.
- Do not expose API keys, cookies, tokens, or credentials.
- Prefer the dedicated `request/aitube-live` branch over temporary pull requests.
