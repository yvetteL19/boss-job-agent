// Read a company's 工商信息 (founding year / size / funding) from BOSS via the
// isolated Chrome for Testing (CDP 9222). Decisive company-quality filter:
// reject 当年新成立 / 0-20人 早期初创 before they reach the approval queue.
//
// Env: BOSS_CDP_PORT (9222), BOSS_AGENT_ROOT (default cwd).
// Usage: node browser/cdp_company.mjs <job_detail_url>
// Prints JSON {founded,size,funding,reg_capital,...} AND caches it in
// data/company_facts.json keyed by job_url. Never touches the user's daily Chrome.
import fs from "node:fs";
const ROOT = process.env.BOSS_AGENT_ROOT || process.cwd();
const PORT = process.env.BOSS_CDP_PORT || "9222";
const jobUrl = process.argv[2];
if (!jobUrl) { console.error("usage: node cdp_company.mjs <job_detail_url>"); process.exit(1); }

const pages = await fetch(`http://127.0.0.1:${PORT}/json/list`).then(r => r.json());
const page = pages.find(p => p.type === "page" && p.url.includes("zhipin.com")) || pages.find(p => p.type === "page");
if (!page) { console.error("no zhipin page on CDP " + PORT); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 1; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id).res(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = id++; pend.set(i, { res: r }); ws.send(JSON.stringify({ id: i, method, params })); });
const sleep = ms => new Promise(r => setTimeout(r, ms));
await new Promise(r => ws.onopen = r);
await send("Page.enable"); await send("Runtime.enable");
await send("Page.navigate", { url: jobUrl }); await sleep(6500);
let r = await send("Runtime.evaluate", { expression: `(()=>{const a=[...document.querySelectorAll('a[href*="/gongsi/"]')].map(x=>x.href).filter(h=>/gongsi\\/[^/]+\\.html/.test(h));return JSON.stringify([...new Set(a)]);})()`, returnByValue: true });
const links = JSON.parse(r.result?.result?.value || "[]");
if (!links[0]) { console.log(JSON.stringify({ error: "no company link" })); ws.close(); process.exit(0); }
await send("Page.navigate", { url: links[0] }); await sleep(6500);
r = await send("Runtime.evaluate", { expression: `(()=>{const t=document.body?document.body.innerText.replace(/\\s+/g,' '):'';
  const m=t.match(/成立时间[:：]?\\s*(\\d{4}-\\d{2}-\\d{2})/)||t.match(/成立[^\\d]{0,8}(\\d{4})/);
  return JSON.stringify({companyUrl:location.href, title:document.title.slice(0,40),
    成立:m?m[1]:'未找到',
    facts:(t.match(/(未融资|天使轮|Pre-A|A轮|B轮|C轮|D轮|已上市|不需要融资|0-20人|20-99人|100-499人|500-999人|1000-9999人|10000人以上)/g)||[]).slice(0,8),
    注册资本:(t.match(/注册资本[:：]?\\s*([\\d.]+万?元?)/)||[])[1]||'',
    head:t.slice(0,300)});})()`, returnByValue: true });
const raw = JSON.parse(r.result?.result?.value || "{}");
const SIZE = ["0-20人","20-99人","100-499人","500-999人","1000-9999人","10000人以上"];
const facts = raw.facts || [];
const out = {
  job_url: jobUrl,
  founded: raw.成立 && raw.成立 !== "未找到" ? raw.成立 : "",
  size: facts.find(f => SIZE.includes(f)) || "",
  funding: facts.find(f => !SIZE.includes(f)) || "",
  reg_capital: raw.注册资本 || "",
  company_url: raw.companyUrl || "",
  checked_at: new Date().toISOString().slice(0, 10),
};
console.log(JSON.stringify(out, null, 2));
const fp = `${ROOT}/data/company_facts.json`;
let cache = {};
if (fs.existsSync(fp)) { try { cache = JSON.parse(fs.readFileSync(fp, "utf8")); } catch {} }
cache[jobUrl] = out;
fs.writeFileSync(fp, JSON.stringify(cache, null, 2));
ws.close();
