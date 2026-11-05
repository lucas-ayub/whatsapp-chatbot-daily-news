// Cloudflare Worker that forwards /whatsapp.php?... to CallMeBot.
// Use it when CallMeBot refuses requests coming from GitHub Actions (HTTP 403):
// the request then leaves from Cloudflare's network instead of GitHub's.
// Setup: see "CallMeBot relay" in README.md.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== "/whatsapp.php") {
      return new Response("callmebot relay ok\n");
    }
    const upstream = await fetch("https://api.callmebot.com/whatsapp.php" + url.search, {
      headers: { "User-Agent": "whatsapp-daily-digest-relay/1.0" },
    });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") || "text/plain" },
    });
  },
};
