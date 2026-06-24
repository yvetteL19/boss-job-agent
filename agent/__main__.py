#!/usr/bin/env python3
"""Unified CLI:  jobagent <command> [args]   (or:  python3 -m agent <command>)

One entry point for the whole workflow. Each subcommand maps to a module and
forwards the remaining args to it, so e.g. `jobagent discover --keywords ...`
behaves exactly like `python3 -m agent.discover --keywords ...`.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys

from .config import ROOT, cfg

# command -> (module, one-line help)
COMMANDS: dict[str, tuple[str, str]] = {
    "discover":  ("agent.discover",              "搜索→读JD→公司体检→硬门，产出待审幸存者"),
    "ingest":    ("agent.ingest",                "把 data/current_page.json 列表卡入台账"),
    "eval":      ("agent.llm_eval",              "把 data/llm_evals.json 的 LLM 判断写回台账"),
    "cards":     ("agent.render_decision_batch", "生成结论先行决策卡 Decision Batch.md"),
    "decide":    ("agent.decide",                "按编号 --approve / --skip"),
    "greet":     ("agent.greetings",             "生成招呼语草稿 data/greetings.json"),
    "send":      ("agent.render_send_queue",     "生成手动发送清单 Send Queue.md + 开页URL"),
    "dashboard": ("agent.render_dashboard",      "生成 Dashboard.md + Approval Queue.md"),
    "review":    ("agent.weekly_review",         "漏斗 + 转化周报"),
    "doctor":    ("agent.healthcheck",           "跑批前体检"),
}


def _usage() -> str:
    width = max(len(c) for c in COMMANDS)
    lines = ["jobagent <command> [args]   —  BOSS 直聘求职 agent（发送永远手动）", "",
             "commands:"]
    for cmd, (_, desc) in COMMANDS.items():
        lines.append(f"  {cmd.ljust(width)}  {desc}")
    lines += ["  open".ljust(width + 2) + "  在隔离浏览器开 approved 标签（node browser/cdp_open.mjs）",
              "", "examples:",
              "  jobagent doctor",
              "  jobagent discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 12",
              "  jobagent decide --approve 1,3 --skip 2",
              "", "每个命令支持 -h 查看自身参数。"]
    return "\n".join(lines)


def _cmd_open() -> int:
    """Open approved-role tabs in the isolated browser (manual send stays manual)."""
    env = os.environ.copy()
    env["BOSS_AGENT_ROOT"] = str(ROOT)
    env["BOSS_LOGIN_NAME"] = str(cfg("identity", "login_name", default="") or "")
    return subprocess.run(["node", str(ROOT / "browser" / "cdp_open.mjs"), *sys.argv[2:]],
                          cwd=ROOT, env=env).returncode


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(_usage())
        return
    cmd = sys.argv[1]
    if cmd == "open":
        sys.exit(_cmd_open())
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        sys.exit(2)
    module_name, _ = COMMANDS[cmd]
    module = importlib.import_module(module_name)
    # Hand the rest of argv to the module's own argparse-based main().
    sys.argv = [f"jobagent {cmd}", *sys.argv[2:]]
    module.main()


if __name__ == "__main__":
    main()
