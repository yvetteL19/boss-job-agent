#!/usr/bin/env python3
"""Render Dashboard.md + Approval Queue.md from the ledger.

Dashboard = funnel counts, the numbered approval queue (decision aid, not auto
permission), active conversations, and follow-ups that have gone stale.

Run:  python3 -m agent.render_dashboard
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from .config import ROOT
from .decide import queue_rows
from .ledger import read_rows
from .rules import decision_action, decision_label, parse_score

DASH = ROOT / "Dashboard.md"
QUEUE = ROOT / "Approval Queue.md"

FUNNEL = ["discovered", "shortlisted", "approved", "applied", "replied", "interview"]
ACTIVE = {"applied", "replied", "interview"}


def _age_days(iso: str) -> int | None:
    try:
        return (date.today() - datetime.fromisoformat(iso).date()).days
    except Exception:
        return None


def render_queue(rows) -> str:
    q = queue_rows(rows)
    lines = ["# Approval Queue", "",
             "> 编号对应 `python3 -m agent.decide --approve N --skip M`。",
             "> 分数是决策辅助，不是自动许可；最终发送永远手动。", ""]
    if not q:
        lines.append("_暂无待审批岗位。先跑 `python3 -m agent.discover` 或 `python3 -m agent.llm_eval`。_")
        return "\n".join(lines) + "\n"
    for i, r in enumerate(q, 1):
        score = parse_score(r.get("match_score")) or 0
        lines.append(f"### {i}. {r['company']} · {r['title']}  —  {r.get('match_score','?')} ({decision_label(score)})")
        meta = " · ".join(x for x in [r.get("salary"), r.get("city"), r.get("experience") or "经验不限"] if x)
        lines.append(f"- {meta}")
        if r.get("fit_reason"):
            lines.append(f"- {r['fit_reason']}")
        lines.append(f"- 建议：{decision_action(score)}")
        lines.append(f"- 🔗 {r['job_url']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_dashboard(rows) -> str:
    counts = Counter(r.get("status") or "unknown" for r in rows)
    q = queue_rows(rows)
    active = [r for r in rows if r.get("status") in ACTIVE]
    stale = [r for r in active
             if (a := _age_days(r.get("applied_at", ""))) is not None and a >= 7
             and r.get("status") == "applied"]

    lines = [f"# Dashboard — {date.today().isoformat()}", "",
             "## 漏斗", ""]
    lines.append("| 阶段 | 数量 |")
    lines.append("|---|---:|")
    for s in FUNNEL:
        lines.append(f"| {s} | {counts.get(s, 0)} |")
    skipped = counts.get("skipped", 0) + counts.get("rejected", 0)
    lines.append(f"| skipped/rejected | {skipped} |")
    lines += ["", f"**待审批：{len(q)}**　**进行中：{len(active)}**　**总计：{len(rows)}**", ""]

    lines += ["## 下一步", ""]
    if q:
        lines.append(f"- 打开 `Approval Queue.md`，回 `approve 1,3` / `skip 2`（共 {len(q)} 个候选）。")
    else:
        lines.append("- 审批队列为空：跑 `python3 -m agent.discover --keywords ... --top 12`。")
    if stale:
        lines.append(f"- ⏰ {len(stale)} 个投递 ≥7 天无进展，考虑跟进或归档。")
    lines.append("")

    if active:
        lines += ["## 进行中", ""]
        for r in sorted(active, key=lambda x: x.get("applied_at", ""), reverse=True):
            age = _age_days(r.get("applied_at", ""))
            tail = f"（{age}天前）" if age is not None else ""
            lines.append(f"- [{r.get('status')}] {r['company']} · {r['title']} {tail}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    rows = read_rows()
    DASH.write_text(render_dashboard(rows), encoding="utf-8")
    QUEUE.write_text(render_queue(rows), encoding="utf-8")
    print(f"wrote {DASH.name} and {QUEUE.name} ({len(rows)} ledger rows)")


if __name__ == "__main__":
    main()
