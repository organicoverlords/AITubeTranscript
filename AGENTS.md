# Agent instructions

For YouTube research execution, do not infer the workflow from source files and do not rediscover repositories.

1. Read [`GPT_FAST_PATH.md`](GPT_FAST_PATH.md) for the canonical request, polling, proof, complete-reading, timing, fallback, and privacy contract.
2. Use [`GPT_MEMORY.md`](GPT_MEMORY.md) when the user asks what persistent instruction to save in ChatGPT.
3. Use `README.md` for human installation and private companion-repository setup.

Core invariants:

- Official GitHub execution must occur in a private repository.
- Generated requests, logs, transcripts, descriptions, comments, manifests, and receipts remain private.
- File existence and workflow success are not completeness proof.
- Verify transcript and comment coverage manifests.
- Open every file listed by `reader-manifest.json` before claiming complete reading.
- Do not expose API keys or cookies.
- Prefer the dedicated `request/aitube-live` branch over temporary pull requests.
