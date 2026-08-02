# Agent instructions

For YouTube research execution, do not infer the workflow from source files and do not rediscover repositories.

1. Read [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) for the canonical single-video, batch, playlist, channel-catalog, polling, proof, reading, timing, fallback, and privacy contract.
2. Read [`BATCH_USAGE.md`](BATCH_USAGE.md) for request examples and limits.
3. Use [`GPT_MEMORY.md`](GPT_MEMORY.md) when the user asks what persistent instruction to save in ChatGPT.
4. Use [`MAGICMUSIC_INSTALL.md`](MAGICMUSIC_INSTALL.md) for the streamlined ChatGPT installer.
5. Use [`INSTALL.md`](INSTALL.md) for manual private companion-repository setup.

Core invariants:

- Official GitHub execution must occur in a private repository.
- Generated requests, logs, transcripts, descriptions, comments, channel catalogs, manifests, and receipts remain private.
- The tool collects research text and metadata; it does not download or redistribute video/audio media.
- File existence and workflow success are not completeness proof.
- Verify video, batch, playlist-expansion, and channel-catalog coverage independently.
- Open every file required by the applicable reader manifest before claiming complete reading.
- Only call a channel catalog complete when `catalog_exhausted = true`.
- Channel reports must include title, publication timestamp/date, duration, video ID/URL, and available snapshot statistics for every selected row.
- Do not expose API keys, cookies, tokens, or credentials.
- Prefer the dedicated `request/aitube-live` branch over temporary pull requests.
