/**
 * Server-sent events over `fetch`.
 *
 * `EventSource` only speaks GET, and both of our streams are POSTs, so the
 * frames are parsed by hand. Unlike the upload flow this one keeps the
 * `event:` name as well as the payload, because the agent stream carries
 * several kinds of frame (`tool`, `text`, `error`, `done`) and the UI reacts
 * differently to each.
 */

export type SseFrame = { event: string; data: unknown };

export async function* streamSse(
  url: string,
  init: RequestInit,
): AsyncGenerator<SseFrame> {
  const response = await fetch(url, {
    ...init,
    headers: {
      // FormData must set its own multipart boundary; forcing JSON here
      // would make the server reject the upload.
      ...(init.body instanceof FormData ? {} : { "content-type": "application/json" }),
      ...init.headers,
    },
  });

  if (!response.ok || !response.body) {
    let detail: string | undefined;
    try {
      detail = (await response.json())?.detail;
    } catch {
      /* the body was not JSON; fall back to the status */
    }
    throw new Error(detail ?? `Request failed (${response.status}).`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normalise CRLF first. sse_starlette's DEFAULT_SEPARATOR is "\r\n", so
    // frames arrive separated by "\r\n\r\n" — splitting on "\n\n" matches
    // nothing at all and silently yields zero events while the request looks
    // perfectly healthy (200, body streaming, no error anywhere). The spec
    // allows CR, LF or CRLF, so the only safe reader normalises.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    // Frames are separated by a blank line. The tail is kept: it is either
    // empty or a partial frame the next read will complete.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      try {
        yield { event, data: JSON.parse(dataLines.join("\n")) };
      } catch {
        /* a malformed frame is skipped rather than killing the stream */
      }
    }
  }
}
