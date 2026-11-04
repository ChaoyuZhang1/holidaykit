// Cloudflare Pages Function: POST /ics-count
// 前端在点击 .ics 订阅链接时用 navigator.sendBeacon 上报，用于统计 ICS 订阅意图。
//
// 注意：Pages Functions 只在「Git 集成部署」或 `wrangler pages functions build` 时生效；
// 直接 `wrangler pages deploy dist` 上传静态目录不包含 functions，此时请求会 404，
// 前端会静默忽略。若要统计，请绑定 Analytics Engine（见 wrangler.toml 注释）。
export async function onRequestPost(context) {
  const { request, env } = context;
  try {
    const body = await request.json();
    if (env.ICS_EVENTS && typeof env.ICS_EVENTS.writeDataPoint === "function") {
      env.ICS_EVENTS.writeDataPoint({
        indexes: ["ics-click"],
        blobs: [String(body && body.href ? body.href : "").slice(0, 200)],
        doubles: [1],
      });
    }
  } catch (_) {
    // 统计失败不影响用户下载
  }
  return new Response(null, {
    status: 204,
    headers: { "access-control-allow-origin": "*" },
  });
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "POST, OPTIONS",
      "access-control-allow-headers": "content-type",
    },
  });
}
