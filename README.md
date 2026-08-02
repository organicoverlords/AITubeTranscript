# AITubeTranscript

Fetch a YouTube video's **full available transcript**, metadata, description, and a bounded sample of comments. Every run writes human-readable files plus a machine-readable proof receipt.

The project is public and reusable. It does not require a paid API key for normal caption retrieval.

## Retrieval ladder

Transcript retrieval runs first so unavailable metadata or comment services cannot delay a usable transcript:

1. `youtube-transcript-api` for manual or automatic captions.
2. Caption tracks exposed by `yt-dlp`, with Deno/EJS challenge solving and alternate non-web clients.
3. The no-key `youtube-transcript.ai` edge endpoint when the runner's IP cannot reach YouTube captions directly.
4. A second no-key hosted transcript fallback.
5. Optional `faster-whisper` audio transcription when captions do not exist.

Metadata and comments use independent fallbacks:

1. Direct `yt-dlp` extraction.
2. Optional official YouTube Data API using `YOUTUBE_API_KEY`.
3. YouTube oEmbed for basic title/channel metadata.
4. Public Piped `/streams` and `/comments` APIs.
5. Public Invidious video and comment APIs.

Each attempt and selected source is written to `receipt.json`. YouTube and public frontends can still block cloud IPs or temporarily fail. The tool reports `NOT_PROVEN` rather than pretending a partial result is complete.

## Fast local use

Python 3.10 or newer:

```bash
pipx install git+https://github.com/organicoverlords/AITubeTranscript.git
aitube-transcript "https://www.youtube.com/watch?v=x8W_S9zmodk" --languages en --comments 100
```

Outputs:

```text
results/<video-id>/
├── transcript.md
├── transcript.txt
├── description.md
├── comments.md
├── result.json
└── receipt.json
```

For videos without captions:

```bash
pipx install "git+https://github.com/organicoverlords/AITubeTranscript.git#egg=aitube-transcript[whisper]"
aitube-transcript VIDEO_URL --whisper --whisper-model tiny
```

The first Whisper run downloads a model. CPU transcription is slower than caption retrieval.

## Reliable descriptions and comments

The Piped and Invidious routes require no key, but public instances can be unavailable. For the most reliable public description and top-level comment retrieval, create a YouTube Data API key and set:

```bash
export YOUTUBE_API_KEY="your-key"
aitube-transcript VIDEO_URL --comments 100
```

Windows PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "your-key"
aitube-transcript VIDEO_URL --comments 100
```

The key is read from the environment or from `--youtube-api-key`. Never commit it.

For GitHub Actions, add a repository Actions secret named `YOUTUBE_API_KEY`. The bundled fetch workflow uses it automatically when present and still works without it.

## GitHub-only use

Fork the repository, open **Actions → Fetch YouTube research bundle → Run workflow**, paste a URL, and run it. Results are committed to the fork's `results` branch under:

```text
videos/<video-id>/latest/
```

This requires no local installation.

### Issue-trigger mode

Repository owners and collaborators can open an issue titled:

```text
[fetch] https://www.youtube.com/watch?v=x8W_S9zmodk
```

The workflow posts a result link back to the issue. Public issue execution is disabled by default to prevent strangers from consuming the repository owner's compute. A maintainer may explicitly enable it by creating the repository variable:

```text
ALLOW_PUBLIC_REQUESTS=true
```

Anyone can still fork the project and use their own Actions runner without that setting.

## Reusable GitHub Action

After a stable release/tag exists, another repository can use:

```yaml
- uses: organicoverlords/AITubeTranscript@v1
  id: youtube
  env:
    YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
  with:
    url: https://www.youtube.com/watch?v=x8W_S9zmodk
    languages: en,fi
    comments: 100
- uses: actions/upload-artifact@v4
  with:
    name: youtube-research
    path: ${{ steps.youtube.outputs.output-directory }}
```

Until `v1` is tagged, pin to a commit SHA.

## Docker

```bash
docker build -t aitube-transcript .
docker run --rm -v "$PWD/results:/app/results" aitube-transcript VIDEO_URL
```

## Cookies and restricted videos

Export a Netscape-format `cookies.txt` locally and pass:

```bash
aitube-transcript VIDEO_URL --cookies /path/to/cookies.txt
```

Never commit cookies. They can grant access to your YouTube account.

## Third-party fallback privacy

When direct YouTube retrieval fails, the tool may send only the public video ID and requested language to hosted transcript providers, Piped, the official Invidious instance registry, and eligible public Invidious instances. It never sends cookies or API keys to these fallback services. The chosen source is visible in the receipt.

## Repository protection

`main` includes CODEOWNERS, a destructive-change guard, SHA-256 integrity manifests, complete Git-bundle backups, and optional mirroring to a separate private repository. See `REPOSITORY_PROTECTION.md` for the branch-rules and deletion-recovery setup.

## What the receipt proves

`receipt.json` includes:

- transcript and comment status (`PROVEN` or `NOT_PROVEN`)
- selected transcript source
- segment and comment counts
- failed fallback attempts and warnings
- SHA-256 hashes for generated files

A successful command does not automatically mean every data class was retrieved. Read the receipt statuses.

## Legal and responsible use

Use the tool for videos you are allowed to access. Respect copyright, privacy, YouTube's terms, and applicable law. Transcripts and comments remain content from their respective creators; the MIT license applies to this software, not to downloaded content.
