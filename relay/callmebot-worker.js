// Cloudflare Worker "callmebot-relay": two jobs.
//
// 1. fetch(): forwards /whatsapp.php?... to CallMeBot. NOT USED for sending: CallMeBot
//    answers requests from Workers with an empty 204 and delivers nothing (see README).
// 2. scheduled(): the daily alarm clock. GitHub's own cron is often hours late or
//    skipped, so Cron Triggers on this Worker (55 5 * * *, 55 6 * * *, 55 7 * * * UTC)
//    start the GitHub workflow with scheduled=true; the workflow itself sends only after
//    07:55 Berlin and only once a day. Needs a Worker secret GITHUB_TOKEN: a fine-grained
//    token for this repository with "Actions: Read and write".
const REPO = "lucas-ayub/whatsapp-chatbot-daily-news";
const UA = "whatsapp-daily-digest-relay/1.0";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== "/whatsapp.php") {
      return new Response("callmebot relay ok\n");
    }
    const upstream = await fetch("https://api.callmebot.com/whatsapp.php" + url.search, {
      headers: { "User-Agent": UA },
    });
    const empty = [101, 204, 205, 304].includes(upstream.status); // statuses that can't carry a body
    return new Response(empty ? null : await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") || "text/plain" },
    });
  },

  async scheduled(event, env) {
    const resp = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/daily.yml/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": UA,
      },
      body: JSON.stringify({ ref: "master", inputs: { scheduled: "true", dry_run: "false" } }),
    });
    console.log(`dispatch for cron "${event.cron}": HTTP ${resp.status} ${await resp.text()}`);
    if (resp.status !== 204) throw new Error(`GitHub dispatch failed: HTTP ${resp.status}`);
  },
};
