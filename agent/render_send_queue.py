#!/usr/bin/env python3
"""Render the send list: one ordered checklist (job + company health + greeting +
checkbox) so you go top-to-bottom without hunting between docs and tabs. Also
writes data/_open_urls.json for browser/cdp_open.mjs.

Greetings come from data/greetings.json {job_url: text} (the send truth source).
SENDING IS ALWAYS MANUAL — this only stages tabs and copy.

Run:  python3 -m agent.render_send_queue
"""

from __future__ import annotations

import json

from .config import COMPANY_FACTS, GREETINGS, OPEN_URLS, ROOT
from .ledger import load_json, read_rows
from .rules import decode_boss_digits

OUT = ROOT / "Send Queue.md"


def main():
    rows = [r for r in read_rows() if r["status"] == "approved"]
    greetings = load_json(GREETINGS, {})
    facts = load_json(COMPANY_FACTS, {})

    body = ["# Send Queue", "",
            "> 已批准、待你手动发送的岗位。在隔离 test 浏览器（已起 `node browser/cdp_open.mjs`）里",
            "> 从上到下：点岗位标签 → 打招呼 → 复制下面招呼语 → 发送 → 勾掉 → 回我「发了 N」。",
            "> 发送永远手动。", ""]
    open_list = []
    if not rows:
        body.append("_当前无 approved 待发岗位。_")
    else:
        for i, r in enumerate(rows, 1):
            url = r["job_url"]
            sal = decode_boss_digits(r.get("salary", ""))
            f = facts.get(url)
            chk = f"（成立{(f.get('founded') or '?')[:4]} · {f.get('size') or '规模?'} · {f.get('funding') or '融资?'}）" if f else ""
            body.append(f"- [ ] **{i}. {r['company']} · {r['title'][:30]}** · {sal} · {r['city'][:8]} {chk}")
            g = greetings.get(url)
            if g:
                body.append("")
                body.append("  ```text")
                for ln in g.splitlines():
                    body.append("  " + ln)
                body.append("  ```")
            else:
                body.append("  ⚠️ 招呼语未写（需先写入 data/greetings.json）")
            body.append(f"  🔗 {url}")
            body.append("")
            open_list.append({"name": f"{r['company']}·{r['title'][:12]}", "url": url})

    OUT.write_text("\n".join(body) + "\n", encoding="utf-8")
    OPEN_URLS.parent.mkdir(parents=True, exist_ok=True)
    OPEN_URLS.write_text(json.dumps(open_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} to send); {OPEN_URLS.name} ({len(open_list)} urls)")


if __name__ == "__main__":
    main()
