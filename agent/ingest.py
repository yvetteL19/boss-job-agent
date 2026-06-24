#!/usr/bin/env python3
"""Import job cards from a captured search page into the ledger as `discovered`.

Reads data/current_page.json (written by browser/cdp_search.mjs via the merge in
discover.py) and parses each card. List cards never auto-promote past
`discovered`; they need JD-body evidence first.

Run:  python3 -m agent.ingest
"""

from __future__ import annotations

import json
import re

from .config import SEARCH_PAGE
from .ledger import canonical_job_key, make_id, read_by_key, today, write_rows
from .rules import FIELDS, decode_boss_digits, summarize_fit

CITY_NAMES = ["上海", "北京", "杭州", "南京", "西安", "深圳", "广州", "苏州", "成都"]


def parse_card(job: dict) -> dict:
    text = decode_boss_digits(job.get("text", ""))
    parts = [p for p in re.split(r"\s+", text) if p]
    title = job.get("title", "").strip() or (parts[0] if parts else "")

    salary = next((p for p in parts if "K" in p or "薪" in p), "")
    experience = next((p for p in parts if "年" in p or p in {"经验不限", "在校/应届"}), "")
    education = next((p for p in parts if p in {"博士", "硕士", "本科", "大专", "学历不限"}), "")

    city = ""
    for p in reversed(parts):
        if any(c in p for c in CITY_NAMES):
            city = p
            break
    company = ""
    if city and city in parts:
        idx = len(parts) - 1 - list(reversed(parts)).index(city)
        if idx > 0:
            company = parts[idx - 1]

    tags: list[str] = []
    if title in parts:
        start = parts.index(title) + 1
        for marker in (salary, experience, education):
            if marker and marker in parts[start:]:
                start = parts.index(marker, start) + 1
        end = parts.index(company) if company and company in parts[start:] else len(parts)
        tags = parts[start:end]

    return {
        "title": title, "company": company, "salary": salary,
        "experience": experience, "education": education,
        "tags": " / ".join(tags), "city": city, "notes": text[:220],
    }


def main() -> None:
    data = json.loads(SEARCH_PAGE.read_text(encoding="utf-8"))
    rows_by_key = read_by_key()
    added = 0
    decision_note = "仅列表页发现；需详情页/JD 复核后再进入审批队列"

    for job in data.get("jobs", [])[:40]:
        url = job.get("href", "")
        if not url:
            continue
        parsed = parse_card(job)
        if parsed["title"] in {"查看更多信息", "职位搜索"} or not parsed["title"] or not parsed["company"]:
            continue
        match_score, fit_reason = summarize_fit(parsed)
        key = canonical_job_key(url)
        row = rows_by_key.get(key, {k: "" for k in FIELDS})
        was_new = key not in rows_by_key
        row.update({
            "id": row.get("id") or make_id(url),
            "job_url": row.get("job_url") or url,
            "platform": row.get("platform") or "BOSS Zhipin",
            "company": parsed["company"], "title": parsed["title"],
            "city": parsed["city"], "salary": parsed["salary"],
            "experience": parsed["experience"], "education": parsed["education"],
            "tags": parsed["tags"], "source_keyword": data.get("keyword", "search"),
            "match_score": match_score, "fit_reason": fit_reason,
            "status": row.get("status") or "discovered",
            "discovered_at": row.get("discovered_at") or today(),
            "notes": row.get("notes") or f"{parsed['notes']} | {decision_note}",
        })
        rows_by_key[key] = row
        if was_new:
            added += 1

    write_rows(list(rows_by_key.values()))
    print(f"Imported {added} new job(s) from {SEARCH_PAGE.name}")


if __name__ == "__main__":
    main()
