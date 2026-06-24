#!/usr/bin/env python3
"""Weekly review: funnel + outcomes, so the strategy can learn from the data.

Summarizes applications sent, replies/interviews, score distribution, and which
source keywords convert. Writes reports/<date>_weekly_review.md. Pair this with
your own reflection on which archetypes/companies to exclude next week (edit
config/profile.yaml accordingly — personalization lives in config, not scripts).

Run:  python3 -m agent.weekly_review
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from .config import REPORT_DIR
from .ledger import read_rows
from .rules import parse_score

ACTIVE = {"applied", "replied", "interview"}


def main():
    rows = read_rows()
    counts = Counter(r.get("status") or "unknown" for r in rows)
    sent = [r for r in rows if r.get("status") in ACTIVE]
    replied = [r for r in rows if r.get("status") in {"replied", "interview"}]
    interview = [r for r in rows if r.get("status") == "interview"]

    by_kw = Counter(r.get("source_keyword", "?") for r in sent)
    scores = [parse_score(r.get("match_score")) or 0 for r in rows if parse_score(r.get("match_score"))]
    avg = round(sum(scores) / len(scores), 2) if scores else 0
    reply_rate = round(100 * len(replied) / len(sent), 1) if sent else 0

    lines = [f"# Weekly Review — {date.today().isoformat()}", "",
             "## 漏斗", "",
             f"- 总台账：{len(rows)}",
             f"- 已发送/投递（applied+）：{len(sent)}",
             f"- 收到回复：{len(replied)}（回复率 {reply_rate}%）",
             f"- 进入面试：{len(interview)}",
             f"- skipped/rejected：{counts.get('skipped',0)+counts.get('rejected',0)}",
             f"- 平均匹配分：{avg}/5", "",
             "## 哪些关键词带来发送", ""]
    if by_kw:
        for kw, n in by_kw.most_common():
            lines.append(f"- {kw}: {n}")
    else:
        lines.append("- 暂无发送记录")
    lines += ["", "## 复盘提示", "",
              "- 回复率高的关键词 → 下周加配额；低的 → 收敛。",
              "- 把反复出现的误报（false positive）公司/方向写进 `config/profile.yaml` 的 hard_filters/lexicon。",
              "- 北极星是 offer，不是发送量。质量优先于凑满每日目标。", ""]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"{date.today().isoformat()}_weekly_review.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
