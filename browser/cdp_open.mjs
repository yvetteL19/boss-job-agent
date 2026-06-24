// Open job_detail pages as tabs in the isolated Chrome for Testing (CDP 9222),
// so you can manually 打招呼/send from that (logged-in) window. Opening pages is
// NOT auto-sending — sending stays 100% manual.
//
// Env: BOSS_CDP_PORT (9222), BOSS_AGENT_ROOT (default cwd).
// Usage: node browser/cdp_open.mjs <url1> <url2> ...
//    or: node browser/cdp_open.mjs        (reads data/_open_urls.json: [{name,url}])
import fs from "node:fs";
const PORT = process.env.BOSS_CDP_PORT || "9222";
const ROOT = process.env.BOSS_AGENT_ROOT || process.cwd();

let items;
if (process.argv.length > 2) {
  items = process.argv.slice(2).map(u => ({ name: "", url: u }));
} else {
  items = JSON.parse(fs.readFileSync(`${ROOT}/data/_open_urls.json`, "utf8"));
}

const ver = await fetch(`http://127.0.0.1:${PORT}/json/version`).then(r => r.json());
const ws = new WebSocket(ver.webSocketDebuggerUrl);
let id = 1; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id).res(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = id++; pend.set(i, { res: r }); ws.send(JSON.stringify({ id: i, method, params })); });
const sleep = ms => new Promise(r => setTimeout(r, ms));
await new Promise(r => ws.onopen = r);
for (const it of items) {
  const r = await send("Target.createTarget", { url: it.url });
  console.log("opened:", it.name || it.url, r.result?.targetId ? "ok" : "FAIL");
  await sleep(3500); // human-paced, avoid bot-detection
}
ws.close();
