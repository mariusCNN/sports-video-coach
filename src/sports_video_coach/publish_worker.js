// Cloudflare Worker in front of the published site (sports-video-coach publish --deploy).
// Static assets answer a Range request with the whole file (200), but Safari / iOS WeChat only play
// <video> and seek <audio> when the server returns 206 Partial Content, so ranges are cut here.
// Every response also gets the security headers below; only GET / HEAD of plain paths reach the assets.
// Training-plan apps (/p/<token>/) also embed YouTube and save their progress to /api/sync/<token> (Workers KV).

// Report pages: inline style and script (each published page also pins its own script by hash in a CSP meta
// tag), Google Fonts, images inlined as data: URIs, audio and clips from the site itself.
const CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src https://fonts.gstatic.com",
  "img-src 'self' data:",
  "media-src 'self' data:",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join("; ");
const SECURITY = {
  "Content-Security-Policy": CSP,
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
  "X-Frame-Options": "DENY",
};

// Plan apps: YouTube players (which refuse to play with error 153 when the page sends no Referer, so the
// origin is sent), their thumbnails, audio from the site itself, and fetch() to the sync API on this site.
const PLAN_CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src https://fonts.gstatic.com",
  "img-src 'self' data: https://i.ytimg.com",
  "media-src 'self'",
  "connect-src 'self'",
  "frame-src https://www.youtube-nocookie.com https://www.youtube.com",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join("; ");
const PLAN_SECURITY = { ...SECURITY, "Content-Security-Policy": PLAN_CSP,
  "Referrer-Policy": "strict-origin-when-cross-origin" };

function secure(response, path = "/") {
  const out = new Response(response.body, response);  // asset responses are immutable; copy to set headers
  const headers = path.startsWith("/p/") ? PLAN_SECURITY : SECURITY;
  for (const [k, v] of Object.entries(headers)) out.headers.set(k, v);
  return out;
}

function plain(status, text) {
  return new Response(text, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

// Encoded slashes, backslashes, dot segments or NUL in the path: never a real asset, refuse them outright.
function badPath(url) {
  const raw = new URL(url).pathname;
  if (/%2f|%5c|%00|\\/i.test(raw)) return true;
  let path;
  try { path = decodeURIComponent(raw); } catch { return true; }
  return path.split("/").some((seg) => seg === ".." || seg === ".");
}

async function serve(request, env) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    const r = plain(405, "method not allowed");
    r.headers.set("Allow", "GET, HEAD");
    return r;
  }
  if (badPath(request.url)) return plain(404, "not found");
  const range = request.headers.get("Range");
  if (!range || request.method !== "GET") return env.ASSETS.fetch(request);
  const headers = new Headers(request.headers);
  headers.delete("Range");
  headers.delete("If-Range");
  const full = await env.ASSETS.fetch(new Request(request.url, { headers }));
  if (full.status !== 200 || full.headers.has("Content-Encoding")) return full;
  const buf = await full.arrayBuffer(), size = buf.byteLength;
  const out = new Headers(full.headers);
  out.set("Accept-Ranges", "bytes");
  const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
  if (!m || (!m[1] && !m[2])) return new Response(buf, { status: 200, headers: out });  // multi-range: whole file
  let start, end;
  if (m[1]) {
    start = Number(m[1]);
    end = m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
  } else {
    start = Math.max(size - Number(m[2]), 0);
    end = size - 1;
  }
  if (start >= size || start > end) {
    out.set("Content-Range", `bytes */${size}`);
    out.delete("Content-Length");
    return new Response(null, { status: 416, headers: out });
  }
  out.set("Content-Range", `bytes ${start}-${end}/${size}`);
  out.set("Content-Length", String(end - start + 1));
  return new Response(buf.slice(start, end + 1), { status: 206, headers: out });
}

// Synced progress of one plan app: the whole log as one JSON document per link token, newest copy wins (the
// page compares `updated`). Only tokens of a published plan are accepted, writes only from the site's own pages.
// A daily copy is kept for 60 days so a bad write can be undone by hand (wrangler kv key get).
const SYNC_MAX = 256 * 1024;
const SYNC_PATH = /^\/api\/sync\/([0-9a-f]{16})$/;

function json(status, text) {
  return new Response(text, { status, headers: { "Content-Type": "application/json; charset=utf-8",
                                                 "Cache-Control": "no-store" } });
}

async function syncApi(request, env, tok) {
  if (!env.SYNC) return plain(404, "not found");
  const page = await env.ASSETS.fetch(new Request(new URL(`/p/${tok}/`, request.url)));
  if (page.status !== 200) return plain(404, "not found");
  const key = `sync:${tok}`;
  if (request.method === "GET" || request.method === "HEAD") {
    return json(200, (await env.SYNC.get(key)) || '{"updated":0}');
  }
  if (request.method !== "PUT") {
    const r = plain(405, "method not allowed");
    r.headers.set("Allow", "GET, HEAD, PUT");
    return r;
  }
  if (request.headers.get("Origin") !== new URL(request.url).origin) return plain(403, "forbidden");
  if (Number(request.headers.get("Content-Length") || 0) > SYNC_MAX) return plain(413, "too large");
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > SYNC_MAX) return plain(413, "too large");
  let doc;
  try { doc = JSON.parse(text); } catch { return plain(400, "not JSON"); }
  if (!doc || typeof doc !== "object" || Array.isArray(doc) || typeof doc.updated !== "number") {
    return plain(400, "expected an object with a numeric updated");
  }
  await env.SYNC.put(key, text);
  const day = `${key}:${new Date().toISOString().slice(0, 10)}`;
  if ((await env.SYNC.get(day)) === null) await env.SYNC.put(day, text, { expirationTtl: 60 * 86400 });
  return json(200, '{"ok":true}');
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const m = SYNC_PATH.exec(path);
    if (m) return secure(await syncApi(request, env, m[1]), path);
    return secure(await serve(request, env), path);
  },
};
