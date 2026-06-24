// Robust CDP job_detail reader for the isolated Chrome for Testing (port 9222).
// Reads URLs from data/_jd_todo.json, navigates each at human pace, extracts
// structured JD + company info, writes data/_jd_reads.json INCREMENTALLY (after
// every job, so a hang never loses progress). Fresh ws per job for resilience.
// Never touches the user's daily Chrome.
//
// Env: BOSS_CDP_PORT (9222), BOSS_AGENT_ROOT (default cwd).
import fs from "node:fs";

const PORT = process.env.BOSS_CDP_PORT || "9222";
const ROOT = process.env.BOSS_AGENT_ROOT || process.cwd();
const FP = `${ROOT}/data/_jd_reads.json`;
const todo = JSON.parse(fs.readFileSync(`${ROOT}/data/_jd_todo.json`, "utf8"));

let done = [];
if (fs.existsSync(FP)) { try { done = JSON.parse(fs.readFileSync(FP, "utf8")); } catch {} }
const doneUrls = new Set(done.map(d => d.url));
const batch = todo.filter(j => !doneUrls.has(j.url));
console.error(`todo=${todo.length} done=${done.length} remaining=${batch.length}`);

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const EXTRACT = `JSON.stringify((() => {
  const q = (s) => document.querySelector(s);
  const t = (el) => el ? (el.innerText || el.textContent || '').trim() : '';
  const jd = t(q('.job-sec-text')) || t(q("[class*='job-sec'] .text")) || t(q("[class*='job-detail'] [class*='text']"));
  const tags = [...document.querySelectorAll('.job-keyword-list li, .tag-all .label-text, [class*=job-tags] *')].map(e=>t(e)).filter(Boolean);
  const comp = t(q('.company-info')) || t(q("[class*='sider-company']")) || t(q("[class*='company-info']"));
  const baseInfo = t(q('.job-primary .info-primary')) || t(q("[class*='info-primary']"));
  return {
    href: location.href, docTitle: document.title,
    title: t(q('.job-name')) || t(q("[class*='job-name']")) || t(q('h1')),
    salary: t(q('.job-salary')) || t(q("[class*='salary']")),
    company: t(q('.company-name')) || t(q("[class*='company-name']")) || t(q("[class*='company'] a")),
    baseInfo, jd, tags: [...new Set(tags)].slice(0,12), companyBlock: comp,
    bodyLen: document.body ? document.body.innerText.length : 0,
    notFound: /该职位已下线|页面不存在|404|职位不存在|已结束/.test(document.body ? document.body.innerText : ''),
  };
})())`;

async function readOne(job) {
  const pages = await fetch(`http://127.0.0.1:${PORT}/json/list`).then(r => r.json());
  const page = pages.find(p => p.type === "page" && p.url.includes("zhipin.com")) || pages.find(p => p.type === "page");
  if (!page) throw new Error("no page target");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 1; const pend = new Map();
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id).res(m); pend.delete(m.id); } };
  function send(method, params = {}) {
    return new Promise((res, rej) => {
      const i = id++;
      const to = setTimeout(() => { pend.delete(i); rej(new Error("cdp timeout " + method)); }, 12000);
      pend.set(i, { res: (v) => { clearTimeout(to); res(v); } });
      ws.send(JSON.stringify({ id: i, method, params }));
    });
  }
  try {
    await Promise.race([new Promise(r => ws.onopen = r), sleep(8000)]);
    await send("Page.enable"); await send("Runtime.enable");
    await send("Page.navigate", { url: job.url });
    await sleep(6500);
    let data = null;
    for (let i = 0; i < 4; i++) {
      try {
        const r = await send("Runtime.evaluate", { expression: EXTRACT, returnByValue: true });
        const v = r.result?.result?.value;
        if (v) { const d = JSON.parse(v); if (d.jd || d.notFound || i === 3) { data = d; break; } }
      } catch (e) { /* retry */ }
      await sleep(2500);
    }
    return data || { error: "no data" };
  } finally { try { ws.close(); } catch {} }
}

for (const job of batch) {
  let data;
  try { data = await readOne(job); }
  catch (e) { data = { error: String(e).slice(0, 120) }; }
  done.push({ url: job.url, company0: job.company, title0: job.title, ...data });
  fs.writeFileSync(FP, JSON.stringify(done, null, 2));
  console.error(`[${done.length}/${todo.length}] ${job.company} :: jd=${(data?.jd || '').length} nf=${data?.notFound} err=${data?.error || ''}`);
  await sleep(3000 + Math.floor(Math.random() * 2500));
}
console.error("done");
process.exit(0);
