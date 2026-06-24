// CDP search reader for the isolated Chrome for Testing on port 9222.
// Navigates the existing BOSS tab to a search URL and extracts job cards, prints
// JSON to stdout. Human-paced waits; never touches the user's daily Chrome.
//
// Env: BOSS_CDP_PORT (default 9222), BOSS_LOGIN_NAME (optional, to verify session).
// Usage: node browser/cdp_search.mjs <searchUrl>
const PORT = process.env.BOSS_CDP_PORT || "9222";
const LOGIN_NAME = process.env.BOSS_LOGIN_NAME || "";
const url = process.argv[2];
if (!url) { console.error("usage: node cdp_search.mjs <searchUrl>"); process.exit(1); }

const pages = await fetch(`http://127.0.0.1:${PORT}/json/list`).then(r => r.json());
const page = pages.find(p => p.type === "page" && p.url.includes("zhipin.com"))
          || pages.find(p => p.type === "page");
if (!page) { console.error("no zhipin page on CDP " + PORT + "; run browser/launch_chrome.sh"); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 1; const pend = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id).res(m); pend.delete(m.id); } };
function send(method, params = {}) { return new Promise(r => { const i = id++; pend.set(i, { res: r }); ws.send(JSON.stringify({ id: i, method, params })); }); }
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

await new Promise(r => ws.onopen = r);
await send("Page.enable");
await send("Runtime.enable");
await send("Page.navigate", { url });
await sleep(8000); // SPA render + security handshake

const nameLit = JSON.stringify(LOGIN_NAME);
const EXTRACT = `JSON.stringify((() => {
  const seen = new Set(); const jobs = [];
  for (const a of document.querySelectorAll('a[href*="/job_detail/"]')) {
    const href = a.href.split('?')[0];
    if (seen.has(href)) continue; seen.add(href);
    const card = a.closest('li, .job-card-wrapper, .job-card-box') || a;
    jobs.push({ href, text: (card.innerText||'').trim().replace(/\\s+/g,' ').slice(0,400) });
  }
  const name = ${nameLit};
  return { url: location.href, title: document.title, jobCount: jobs.length, jobs,
    loggedIn: (name && document.body) ? new RegExp(name).test(document.body.innerText) : null,
    bodyLen: document.body ? document.body.innerText.length : 0 };
})())`;

let data = null;
for (let i = 0; i < 6; i++) {
  await send("Runtime.evaluate", { expression: "window.scrollTo(0, document.body.scrollHeight)" });
  await sleep(1500);
  const r = await send("Runtime.evaluate", { expression: EXTRACT, returnByValue: true });
  const val = r.result?.result?.value;
  if (val) { try { const d = JSON.parse(val); data = d; if (d.jobCount > 0) break; } catch {} }
  await sleep(2000);
}
console.log(data ? JSON.stringify(data) : JSON.stringify({ ok: false, error: "no data" }));
ws.close();
