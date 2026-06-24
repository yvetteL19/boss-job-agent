#!/usr/bin/env python3
"""One-pass discovery orchestrator — front-load ALL machine work into one command.

  search -> ingest -> rule pre-filter -> read JD -> read company -> deterministic
  gate -> emit a packet of survivors for the human's FIT / product-moat judgment.

Why a packet, not auto-approve: role-fit and product moat are judgment calls
(docs/SCREENING_RUBRIC.md). The script removes every deterministic dud (hard
filters + company red lines) so the human only judges real candidates.

Requires the isolated Chrome for Testing on CDP 9222 (see docs/SAFETY.md and
browser/launch_chrome.sh). Never touches your daily Chrome.

Run:
  python3 -m agent.discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 12
  python3 -m agent.discover --from-cache --top 12     # skip network, re-gate pool
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse

from . import config, ingest
from .config import (BATCH_PACKET, COMPANY_FACTS, JD_READS, JD_TODO, ROOT,
                     SEARCH_PAGE, cfg)
from .ledger import load_json, read_rows
from .rules import (classify_archetype, company_quality_flags, decode_boss_digits,
                    hard_filter_reasons, parse_score, scoring_text)

BROWSER = ROOT / "browser"


def _node_env() -> dict:
    env = os.environ.copy()
    env["BOSS_AGENT_ROOT"] = str(ROOT)
    env["BOSS_LOGIN_NAME"] = str(cfg("identity", "login_name", default="") or "")
    return env


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}", file=sys.stderr)
    if cmd and str(cmd[0]) == "node":
        kw.setdefault("env", _node_env())
    return subprocess.run(cmd, cwd=ROOT, **kw)


def search_url(query: str, city: str, page: str = "1") -> str:
    codes = cfg("search", "city_codes", default={}) or {}
    code = codes.get(city, city)
    qs = urllib.parse.urlencode({"query": query, "city": code, "page": page})
    return f"https://www.zhipin.com/web/geek/jobs?{qs}"


def stage_search(keywords, cities):
    """Drive cdp_search.mjs per keyword/city; merge cards into current_page.json."""
    merged: list[dict] = []
    seen: set[str] = set()
    for kw in keywords:
        for city in cities:
            url = search_url(kw, city)
            proc = run(["node", str(BROWSER / "cdp_search.mjs"), url],
                       capture_output=True, text=True, timeout=120)
            try:
                data = json.loads((proc.stdout or "").strip() or "{}")
            except json.JSONDecodeError:
                print(f"    ! parse failed for {kw}/{city}: {proc.stderr[:160]}", file=sys.stderr)
                data = {}
            for j in data.get("jobs", []):
                href = j.get("href", "")
                if href and href not in seen:
                    seen.add(href)
                    merged.append(j)
            time.sleep(4)
    SEARCH_PAGE.write_text(json.dumps({"jobs": merged, "keyword": ",".join(keywords)},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    ingest.main()


def prefilter(top: int):
    rows = read_rows()
    read_urls = {j["url"] for j in load_json(JD_READS, [])}
    seniority = cfg("search", "seniority_excludes", default=[]) or []
    on_strategy = cfg("search", "on_strategy_hints", default=[]) or []
    order = {"A": 0, "B": 1, "unknown": 2}
    cand = []
    for r in rows:
        if r["status"] != "discovered":
            continue
        if "[JD判否]" in r.get("notes", ""):
            continue
        if any(s in r["title"] for s in seniority):
            continue
        if hard_filter_reasons(r, str(ROOT)):
            continue
        _, tier, _, _ = classify_archetype(r, scoring_text(r, str(ROOT)))
        onstrat = any(k in r["title"] for k in on_strategy)
        if not (tier in ("A", "B") or (tier == "unknown" and onstrat)):
            continue
        already = r["job_url"] in read_urls
        cand.append((order[tier], -(parse_score(r["match_score"]) or 0), already, r))
    cand.sort(key=lambda x: (x[0], x[1], x[2]))
    return [c[3] for c in cand[:top]]


def stage_read(cands):
    JD_TODO.write_text(json.dumps(
        [{"url": r["job_url"], "company": r["company"], "title": r["title"]} for r in cands],
        ensure_ascii=False), encoding="utf-8")
    run(["node", str(BROWSER / "cdp_detail.mjs")], capture_output=True, text=True, timeout=600)
    facts = load_json(COMPANY_FACTS, {})
    for r in cands:
        if r["job_url"] in facts:
            continue
        run(["node", str(BROWSER / "cdp_company.mjs"), r["job_url"]],
            capture_output=True, text=True, timeout=120)
        time.sleep(3)


def gate(cands):
    jd_by = {j["url"]: j for j in load_json(JD_READS, [])}
    facts_by = load_json(COMPANY_FACTS, {})
    survivors, rejected = [], []
    for r in cands:
        url = r["job_url"]
        jd = decode_boss_digits((jd_by.get(url, {}) or {}).get("jd", "") or "")
        facts = facts_by.get(url)
        flags = company_quality_flags(facts, jd, r["company"])
        rec = {"url": url, "company": r["company"], "title": r["title"],
               "salary": decode_boss_digits(r.get("salary", "")), "city": r["city"],
               "experience": r["experience"], "jd": jd[:600],
               "company_facts": facts, "company_flags": flags,
               "company_checked": facts is not None}
        (rejected if flags else survivors).append(rec)
    return survivors, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default="")
    ap.add_argument("--cities", default=",".join(cfg("search", "cities", default=["上海"]) or ["上海"]))
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--from-cache", action="store_true", help="skip network; re-gate existing pool")
    args = ap.parse_args()
    config.ensure_dirs()

    if not args.from_cache and args.keywords:
        print("[1] 搜索 + 入台账 ...", file=sys.stderr)
        stage_search([k.strip() for k in args.keywords.split(",") if k.strip()],
                     [c.strip() for c in args.cities.split(",") if c.strip()])

    print("[2] 规则预筛 ...", file=sys.stderr)
    cands = prefilter(args.top)
    print(f"    候选 {len(cands)}", file=sys.stderr)

    if not args.from_cache:
        print("[3] 读 JD + 公司体检 ...", file=sys.stderr)
        stage_read(cands)

    print("[4] 确定性硬门 ...", file=sys.stderr)
    survivors, rejected = gate(cands)
    BATCH_PACKET.write_text(json.dumps({"survivors": survivors, "rejected": rejected},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n决策就绪幸存者 {len(survivors)}（公司硬门毙 {len(rejected)}）→ {BATCH_PACKET}")
    print("下一步：人审 survivors 的 JD-fit/产品壁垒/专业相关 → 设 shortlisted → python3 -m agent.render_decision_batch")
    for s in survivors:
        chk = "公司未核" if not s["company_checked"] else "✅"
        print(f"  [{chk}] {s['company'][:14]} | {s['title'][:24]} | {s['salary']}")


if __name__ == "__main__":
    main()
