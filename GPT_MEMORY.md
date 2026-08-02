# GPT memory instructions

Copy one of these blocks into ChatGPT and ask it to remember the instruction for future YouTube research requests.

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

Fast path:
1. Extract the YouTube video ID from the supplied URL.
2. Read organicoverlords/all/aitube-requests/current.json from request/aitube-live and retain its current blob SHA.
3. Replace it on the same branch with a unique request_id, the full video_url, languages=en unless another language is requested, comments=100 unless another number is requested, and whisper=false unless captions are unavailable.
4. The direct commit triggers the private GitHub workflow. Do not create a temporary PR unless this trigger fails.
5. Poll videos/<video-id>/latest/receipt.json on the aitube-results branch and confirm fetched_at or the blob SHA changed so an old result is not mistaken for the new run.
6. Require transcript_status=PROVEN and transcript_coverage_status=PROVEN. When comments were requested, require comments_status=PROVEN and comments_coverage_status=PROVEN.
7. Read reader-manifest.json, then open and consume every file in read_order. Prefer parallel_read_groups when supported.
8. Verify transcript-manifest.json and comments-manifest.json: coverage.status=PROVEN, exactly_once=true, missing_indices=[], duplicate_indices=[], unexpected_indices=[], and ordered_contiguous=true.
9. Only claim “I read every word” after every reader file has actually been opened and consumed.
10. Report request-to-fetch-complete, fetch-complete-to-reading-complete, and total request-to-reading-complete separately. State when the benchmark start has only minute-level precision.
11. Report title, channel, publication date, duration, snapshot views, likes, total comment count, retrieved segment and comment counts, description size, coverage evidence, a concise summary, and dominant comment themes.
12. Distinguish retrieval completeness from transcript textual accuracy. Third-party or automatic transcript accuracy remains NOT_PROVEN. Mention visible transcription defects and verify important quotations against the video.
13. Use the fast-cloud path first, the fallback ladder only when needed, and Whisper only when captions cannot be retrieved.
14. Keep all requests, workflow logs, transcripts, descriptions, comments, and receipts private. Never publish them to organicoverlords/AITubeTranscript and never expose API keys or cookies.
15. Avoid repository discovery, repeated README reads, full result.json retrieval, full repository clones, unrelated workflow polling, rereading unchanged files, and temporary PRs when the direct request branch works.

The full operating contract is in organicoverlords/AITubeTranscript/GPT_FAST_PATH.md. Read it only when this memory is missing, ambiguous, or the fast path fails.
```

## Generic instruction for another user

Replace the placeholders before saving this memory:

```text
For future YouTube research requests, use the optimized private AITubeTranscript workflow.

Canonical locations:
- Public tool source: organicoverlords/AITubeTranscript
- Private execution and results repository: <OWNER>/<PRIVATE_REPOSITORY>
- Preferred private request branch: request/aitube-live
- Request file: aitube-requests/current.json
- Private results branch: aitube-results

Do not search for the repositories or reread setup documentation unless the fast path fails.

For each YouTube URL, update the private request file with a unique request_id, full video_url, requested languages, comment limit, and whisper=false. Poll the matching private receipt, require PROVEN transcript and comment coverage, read reader-manifest.json, consume every file in read_order, verify both coverage manifests, and only then claim complete reading. Keep all generated data, logs, API keys, and cookies private. Use organicoverlords/AITubeTranscript/GPT_FAST_PATH.md only when the saved fast path fails or needs repair.
```

## What should and should not be stored as memory

Store stable workflow facts:

- canonical repositories and branches
- request and result paths
- privacy requirements
- proof gates
- reading and timing rules
- fallback order

Do not store:

- the API key value
- cookies or authentication tokens
- one-time workflow run IDs
- temporary commit SHAs
- video-specific transcripts or comments
- transient error logs
