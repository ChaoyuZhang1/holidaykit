// Cloudflare Pages Function: GET /geo
// Uses Cloudflare's edge geolocation (request.cf) — no external API, no cookies.
export async function onRequestGet(context) {
  const { request } = context;
  const cf = request.cf || {};
  const payload = {
    country: (cf.country || "").toUpperCase(),
    timezone: cf.timezone || "",
    city: cf.city || "",
    region: cf.region || "",
    continent: cf.continent || "",
  };
  return new Response(JSON.stringify(payload), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
    },
  });
}
