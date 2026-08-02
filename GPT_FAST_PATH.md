# GPT fast path for private YouTube research

This is the canonical operating contract for GPT or another agent that has GitHub access.

## Canonical repositories for this deployment

- Public tool source: `organicoverlords/AITubeTranscript`
- Private execution and results repository: `organicoverlords/all`
- Private request branch: `request/aitube-live`
- Private results branch: `aitube-results`

Do not search for these repositories or reread setup documentation unless the fast path fails.

## Fast request path

1. Extract the 11-character YouTube video ID from the supplied URL.
2. Read `aitube-requests/current.json` from `organicoverlords/all` on branch `request/aitube-live` and retain its current blob SHA.
3. Replace that file on the same branch with a request containing:

```json
{
  "request_id": "unique-id",
  "video_url": "full YouTube URL",
  "languages": "en",
  "comments": 100,
  "whisper": false
}
```

Use the requested language or comment count when the user specifies one. Leave `whisper` false unless captions cannot be retrieved.

4. The direct commit to `request/aitube-live` triggers the private workflow. Do not create a temporary pull request unless the branch trigger fails.
5. Poll `videos/<video-id>/latest/receipt.json` on the private `aitube-results` branch. Compare `fetched_at` or the blob SHA with the previous result so an older run is not mistaken for the new request.
6. Do not poll unrelated workflow metadata when the result file itself is sufficient. Inspect workflow runs or logs only when the result does not update within a reasonable interval.

Fallback trigger order:

1. direct update of `request/aitube-live`
2. direct update of `main/aitube-requests/current.json`
3. same-repository request pull request
4. manual `workflow_dispatch`

## Completeness gates

File existence and workflow success do not prove completeness.

Require from `receipt.json`:

- `transcript_status = PROVEN`
- `transcript_coverage_status = PROVEN`
- `comments_status = PROVEN` when comments were requested
- `comments_coverage_status = PROVEN` when comments were retrieved

Read `transcript-manifest.json` and require:

- `coverage.status = PROVEN`
- `coverage.exactly_once = true`
- `coverage.missing_indices = []`
- `coverage.duplicate_indices = []`
- `coverage.unexpected_indices = []`
- `coverage.ordered_contiguous = true`

Read `comments-manifest.json` and require the equivalent comment coverage fields when comments were requested.

## Complete reading contract

1. Read `reader-manifest.json` first.
2. Open and consume every file listed in `read_order`:
   - `description.md`
   - every transcript chunk
   - every comment chunk
3. Use `parallel_read_groups` to open independent bounded files concurrently when the connector supports parallel calls.
4. Do not retrieve the large `result.json` unless a field is unavailable elsewhere; it may be truncated by connectors.
5. Do not reread a file that was already returned completely and whose hash has not changed.
6. Only claim **“I read every word”** after every reader file has actually been opened and consumed.

## Timing contract

Record these separately:

- request-to-fetch-complete
- fetch-complete-to-reading-complete
- total request-to-reading-complete

Use the user-message timestamp as the benchmark start only when its precision is known. State explicitly when the start time has only minute-level precision. Prefer an exact timestamp captured immediately before the request-file write.

## Required report

Report:

- video title, channel, publication date, and duration
- snapshot views, likes, and total comment count when available
- retrieved transcript segment count
- retrieved comment count
- description size
- transcript and comment coverage evidence
- concise video summary
- dominant themes across fetched comments
- the three timing measurements

Distinguish these claims:

- **Retrieval completeness:** may be `PROVEN` by the manifests.
- **Transcript textual accuracy:** remains `NOT_PROVEN` when the transcript came from a third-party provider or automatic captions.

Mention visible transcription defects such as repeated words, punctuation problems, malformed timestamps, or incorrect names. Important quotations must be checked against the original video before being treated as exact.

## Failure and privacy rules

- Use the fast-cloud transcript path first.
- Use the repository fallback ladder only when the fast path fails.
- Enable Whisper only when captions cannot be retrieved.
- Never publish transcripts, descriptions, comments, receipts, request files, or workflow logs to the public `AITubeTranscript` repository.
- Keep generated research in the private execution repository.
- Never print or commit `YOUTUBE_API_KEY`, cookies, or other credentials.

## Speed rules

Avoid:

- GitHub repository discovery
- repeated README inspection
- full private-repository clones
- full-history fetches
- full `result.json` retrieval when smaller proof files are available
- sequential polling of unrelated workflow data
- rereading unchanged content
- temporary PR creation when the direct request branch works
