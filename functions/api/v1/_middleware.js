// Edge rate limiter for the public JSON API.
// Static responses are served by env.ASSETS / next(); this middleware only
// throttles bursts so a single client cannot hammer the whole dataset.
//
// Note: counters live in the isolate handling the request, so the effective
// limit is per-isolate across Cloudflare's edge PoPs. That is enough to stop
// scripted scraping bursts; a global quota would need KV/Durable Objects.

const LIMIT = 240;            // requests per window per client IP
const WINDOW_MS = 60_000;     // 1 minute
const MAX_KEYS = 5000;        // bound memory per isolate
const buckets = new Map();

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,HEAD,OPTIONS",
    "Access-Control-Allow-Headers": "*",
  };
}

export async function onRequest(context) {
  const { request } = context;

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const now = Date.now();
  let bucket = buckets.get(ip);

  if (!bucket || now - bucket.start > WINDOW_MS) {
    if (buckets.size > MAX_KEYS) {
      for (const [key, value] of buckets) {
        if (now - value.start > WINDOW_MS) buckets.delete(key);
      }
    }
    bucket = { start: now, count: 0 };
    buckets.set(ip, bucket);
  }

  bucket.count += 1;

  if (bucket.count > LIMIT) {
    const retryAfter = Math.max(1, Math.ceil((bucket.start + WINDOW_MS - now) / 1000));
    return new Response(
      JSON.stringify({
        error: "rate_limited",
        message: "Too many requests. Please cache responses and retry later.",
        limit: LIMIT,
        window: "60s",
        retryAfter,
      }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Retry-After": String(retryAfter),
          "Cache-Control": "no-store",
          ...corsHeaders(),
        },
      }
    );
  }

  const response = await context.next();
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "public, max-age=86400");
  headers.set("X-RateLimit-Limit", String(LIMIT));
  headers.set("X-RateLimit-Remaining", String(Math.max(0, LIMIT - bucket.count)));
  for (const [key, value] of Object.entries(corsHeaders())) headers.set(key, value);
  return new Response(response.body, { status: response.status, headers });
}
