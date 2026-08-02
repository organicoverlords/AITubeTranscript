import { Innertube, UniversalCache } from "npm:youtubei.js@17.0.1";

const videoId = Deno.args[0];
const requestedLimit = Number.parseInt(Deno.args[1] ?? "100", 10);
const commentLimit = Number.isFinite(requestedLimit)
  ? Math.max(0, Math.min(500, requestedLimit))
  : 100;

if (!videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
  console.error("A valid 11-character YouTube video ID is required.");
  Deno.exit(2);
}

function textValue(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["text", "name", "title", "content"]) {
      const candidate = textValue(record[key]);
      if (candidate) return candidate;
    }
    if (Array.isArray(record.runs)) {
      const joined = record.runs
        .map((run) => textValue(run))
        .filter((item): item is string => Boolean(item))
        .join("");
      if (joined.trim()) return joined.trim();
    }
  }
  try {
    const rendered = String(value).trim();
    return rendered && rendered !== "[object Object]" ? rendered : null;
  } catch {
    return null;
  }
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const rendered = textValue(value);
  if (!rendered) return null;
  const compact = rendered.replace(/,/g, "").trim().toUpperCase();
  const match = compact.match(/^([0-9]+(?:\.[0-9]+)?)\s*([KMB])?$/);
  if (!match) return null;
  const base = Number.parseFloat(match[1]);
  const multiplier = match[2] === "K"
    ? 1_000
    : match[2] === "M"
    ? 1_000_000
    : match[2] === "B"
    ? 1_000_000_000
    : 1;
  return Math.round(base * multiplier);
}

function authorName(author: unknown): string | null {
  if (!author || typeof author !== "object") return textValue(author);
  const record = author as Record<string, unknown>;
  return textValue(record.name) ?? textValue(record.title) ?? textValue(author);
}

const output: {
  metadata: Record<string, unknown>;
  comments: Array<Record<string, unknown>>;
  warnings: string[];
} = {
  metadata: {},
  comments: [],
  warnings: [],
};

try {
  const youtube = await Innertube.create({
    cache: new UniversalCache(false),
    generate_session_locally: true,
  });

  try {
    const info = await youtube.getBasicInfo(videoId, { client: "TV" });
    const basic = info.basic_info;
    output.metadata = {
      id: videoId,
      title: basic.title ?? null,
      description: basic.short_description ?? null,
      channel: basic.channel?.name ?? basic.author ?? null,
      uploader: basic.channel?.name ?? basic.author ?? null,
      channel_id: basic.channel?.id ?? basic.channel_id ?? null,
      channel_url: basic.channel?.url ?? null,
      duration: basic.duration ?? null,
      view_count: basic.view_count ?? null,
      like_count: basic.like_count ?? null,
      tags: basic.tags ?? basic.keywords ?? null,
      thumbnail: basic.thumbnail?.at(-1)?.url ?? null,
      webpage_url: `https://www.youtube.com/watch?v=${videoId}`,
    };
  } catch (error) {
    output.warnings.push(`metadata: ${error instanceof Error ? error.message : String(error)}`);
  }

  if (commentLimit > 0) {
    try {
      let commentsPage = await youtube.getComments(videoId, "TOP_COMMENTS");
      while (output.comments.length < commentLimit) {
        for (const thread of commentsPage.contents) {
          const comment = thread.comment;
          const content = textValue(comment?.content);
          if (!content) continue;
          output.comments.push({
            author: authorName(comment?.author),
            text: content,
            like_count: numericValue(comment?.like_count),
            published_time: textValue(comment?.published_time),
            comment_id: comment?.comment_id ?? null,
            parent: null,
          });
          if (output.comments.length >= commentLimit) break;
        }
        if (output.comments.length >= commentLimit || !commentsPage.has_continuation) break;
        commentsPage = await commentsPage.getContinuation();
      }
    } catch (error) {
      output.warnings.push(`comments: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
} catch (error) {
  output.warnings.push(`session: ${error instanceof Error ? error.message : String(error)}`);
}

console.log(JSON.stringify(output));
