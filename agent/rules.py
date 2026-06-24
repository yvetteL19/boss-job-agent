#!/usr/bin/env python3
"""Archetype-gated band scoring + hard filters — driven entirely by config.

Scoring is five steps (see ARCHITECTURE.md):
  1. classify_archetype  -> (label, tier, confidence, reasons)
  2. tier base score
  3. bounded evidence modifiers (never cross tiers)
  4. JD-aware hard caps (experience, opacity, content/community, etc.)
  5. confidence / JD-evidence gate

All term sets, tier bases, modifier weights and filter thresholds come from
config/profile.yaml via agent.config. Keyword rules are a SAFETY NET; the real
fit call is the LLM-judge layer (agent/llm_eval.py). Keep the public API stable:
it is consumed by ingest/discover/decide/render/llm_eval.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Mapping
from pathlib import Path

from .config import cfg, lex

FIELDS = [
    "id", "job_url", "platform", "company", "title", "city", "salary",
    "experience", "education", "tags", "source_keyword", "match_score",
    "fit_reason", "archetype", "archetype_conf", "status", "discovered_at",
    "shortlisted_at", "applied_at", "last_checked_at", "next_followup_at",
    "apply_run_id", "apply_outcome", "submitted", "confirmation_status",
    "screenshot_path", "reply_status", "interaction_direction",
    "interview_status", "notes",
]

EXP_FIELD_MIN = {
    "在校/应届": 0, "1年以内": 0, "经验不限": 0, "1-3年": 1,
    "3-5年": 3, "5-10年": 5, "10年以上": 10,
}


# --------------------------------------------------------------------------- #
# Basic helpers
# --------------------------------------------------------------------------- #
def _any(text: str, terms: list[str]) -> bool:
    return any(t in text for t in terms)


def row_text(row: Mapping[str, str]) -> str:
    keys = ("title", "company", "city", "salary", "experience", "education", "tags", "notes")
    return " ".join(str(row.get(k, "")) for k in keys).lower()


def decode_boss_digits(text: str) -> str:
    """BOSS obfuscates salary digits in a private-use unicode block; decode them."""
    table = {chr(0xE030 + d): str(d) for d in range(10)}
    return "".join(table.get(c, c) for c in text)


def parse_score(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"\d+(?:\.\d+)?", value)
    return float(m.group(0)) if m else None


def parse_salary_floor(salary: str) -> int | None:
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*K", salary or "", re.IGNORECASE)
    if m:
        return int(m.group(1))
    single = re.search(r"(\d+)\s*K", salary or "", re.IGNORECASE)
    return int(single.group(1)) if single else None


def salary_floor_of(row: Mapping[str, str]) -> int | None:
    return parse_salary_floor(str(row.get("salary", "")))


def has_approval_surface(text: str) -> bool:
    return _any(text, lex("approval_surface"))


def report_paths(row: Mapping[str, str], root: str | Path | None = None) -> list[Path]:
    if root is None:
        return []
    base = Path(root)
    out: list[Path] = []
    for m in re.findall(r"report=([^ |\n]+)", str(row.get("notes", ""))):
        p = base / m
        if p.exists():
            out.append(p)
    return out


def _report_jd_sections(raw: str) -> str:
    sections: list[str] = []
    for heading in ("## JD Excerpt", "## Positive Evidence From JD", "## Risk Evidence From JD"):
        m = re.search(re.escape(heading) + r"\n(.*?)(?:\n## |\Z)", raw, flags=re.S)
        if m:
            sections.append(m.group(1))
    return "\n".join(sections) if sections else raw


def scoring_text(row: Mapping[str, str], root: str | Path | None = None) -> str:
    text = row_text(row)
    for p in report_paths(row, root):
        try:
            text += "\n" + _report_jd_sections(p.read_text(encoding="utf-8")).lower()
        except OSError:
            continue
    return text


def extract_experience_years(text: str | None) -> int | None:
    """Minimum required years from free text. Ranges contribute their LOW bound."""
    text = (text or "").lower()
    mins: list[int] = []
    for m in re.finditer(r"(\d+)\s*[-~～至到]\s*\d+\s*年", text):
        mins.append(int(m.group(1)))
    for m in re.finditer(r"(\d+)\s*年(?:及以上|以上|\+|起步|起)", text):
        mins.append(int(m.group(1)))
    if any(t in text for t in ("1年以内", "一年以内", "经验不限", "应届", "在校")):
        mins.append(0)
    return max(mins) if mins else None


def required_years(row: Mapping[str, str], text: str) -> int | None:
    cands: list[int] = []
    field_min = EXP_FIELD_MIN.get(str(row.get("experience", "")).strip())
    if field_min is not None:
        cands.append(field_min)
    extracted = extract_experience_years(text)
    if extracted is not None:
        cands.append(extracted)
    return max(cands) if cands else None


def is_intern_or_parttime(row: Mapping[str, str], text: str) -> bool:
    title = str(row.get("title", "")).lower()
    if any(t in title for t in ("实习", "兼职", "实习生")):
        return True
    strong = ("招聘实习", "实习岗位", "本岗位为实习", "实习期", "实习薪", "可转正",
              "兼职", "4天/周", "5天/周")
    return any(t in text for t in strong)


def has_major_mismatch(text: str) -> bool:
    if not _any(text, lex("major_mismatch")):
        return False
    if any(w in text for w in ("优先", "加分", "等专业", "专业不限", "不限专业", "相关专业")):
        return False
    return True


def is_higher_ed_or_gov(company: str, text: str) -> bool:
    comp = (company or "").lower()
    if _any(comp, lex("higher_ed")):
        return True
    return _any(comp + " " + (text or ""), lex("gov_soe"))


def is_early_stage(text: str) -> bool:
    t = (text or "").lower()
    if _any(t, lex("established")):
        return False
    return _any(t, lex("early_stage"))


# --------------------------------------------------------------------------- #
# Freshness / HR-activity (structured signal; never folded into match_score)
# --------------------------------------------------------------------------- #
_HR_ACTIVITY_MAP = [
    (("在线", "刚刚活跃", "今日活跃", "今日活"), "today"),
    (("3日内活跃", "三日内活跃", "近3日", "近三日活跃", "本周活跃", "7日内活跃"), "week"),
    (("本月活跃", "近一月活跃", "2周内活跃", "两周内活跃", "14日内活跃"), "month"),
    (("月内活跃", "2月内活跃", "两月内活跃", "近半年活跃", "半年前活跃", "半年内活跃", "月前活跃"), "stale"),
]


def parse_hr_activity(text: str | None) -> str:
    if not text:
        return "unknown"
    t = text.lower()
    for needles, level in _HR_ACTIVITY_MAP:
        if any(n.lower() in t for n in needles):
            return level
    return "unknown"


def freshness_signal(hr_active, posting_age_days=None, is_junior=False):
    """Return (level, emoji, reasons): fresh/ok/watch/zombie/unknown."""
    hr = hr_active if hr_active in {"today", "week", "month", "stale", "unknown"} else parse_hr_activity(hr_active)
    age = posting_age_days
    old = age is not None and age > 14
    very_old = age is not None and age > 30
    if hr == "stale":
        return ("zombie", "🔴", ["HR 长期未活跃（疑似僵尸岗）"])
    if hr == "today":
        return ("fresh", "🟢", ["HR 今日活跃/在线"])
    if hr == "week":
        if old and not is_junior:
            return ("ok", "🟡", ["HR 本周活跃，但发布偏久"])
        return ("fresh", "🟢", ["HR 本周活跃"])
    if hr == "month":
        if very_old and not is_junior:
            return ("watch", "🟡", ["HR 本月活跃但发布很久，留意"])
        return ("ok", "🟡", ["HR 本月活跃"])
    if is_junior:
        return ("unknown", "⚪", ["校招/应届，时效放宽；HR 活跃未知"])
    if very_old:
        return ("zombie", "🔴", ["发布很久且 HR 活跃未知（疑似僵尸岗）"])
    if old:
        return ("watch", "🟡", ["发布偏久，HR 活跃未知"])
    return ("unknown", "⚪", ["时效/HR 活跃信息缺失，建议发现时抓取"])


# --------------------------------------------------------------------------- #
# Archetype classification
# --------------------------------------------------------------------------- #
def classify_archetype(row: Mapping[str, str], text: str | None = None):
    """Return (label, tier, confidence, reasons). tier in {A,B,C,D,unknown}."""
    if text is None:
        text = row_text(row)
    title = str(row.get("title", "")).lower()
    notes = str(row.get("notes", "")).lower()

    has_ai = _any(text, lex("ai"))
    has_content = _any(text, lex("content_exec")) or _any(title, lex("content_exec"))
    has_community = _any(text, lex("community_ops"))
    has_sales = _any(text, lex("weak_role"))
    has_edu = _any(text, lex("edu_lang"))
    has_product_title = _any(title, lex("product_title"))
    has_ops_signal = _any(text, lex("product_ops_signal"))
    tool_hits = sum(1 for t in lex("tool_eval_ownership") if t in text)
    prod_hits = sum(1 for t in lex("content_production") if t in text)
    has_ownership = tool_hits >= 2 and tool_hits >= prod_hits

    jd_evidenced = bool(
        re.search(r"report=", notes)
        or any(k in text for k in ("职位描述", "岗位职责", "任职", "职位要求", "工作内容", "工作职责"))
    )
    confidence = "high" if jd_evidenced else "med"

    if has_sales and not has_product_title and not has_ownership:
        return ("销售/BD/客服/教师/行政", "D", confidence, ["弱匹配执行/销售类岗位"])
    if has_community and not has_product_title:
        return ("社区/社群运营", "D", confidence, ["社群运营为主的执行岗"])

    if has_content and not has_product_title:
        if has_ownership:
            return ("内容相邻但有产品/工具 ownership", "B", confidence, ["有产品/工具 ownership 的内容相邻岗"])
        return ("内容运营/创作/新媒体内容", "C", confidence, ["内容生产/运营为主，默认跳过"])

    has_growth = _any(text, lex("growth")) or _any(title, lex("growth"))
    has_growth_exec = _any(text, lex("growth_execution"))
    has_growth_own = has_ownership or _any(text, lex("growth_strategy"))
    if has_growth and has_growth_exec and not has_growth_own:
        return ("增长执行（投放/买量/素材）", "C", confidence, ["投放/买量/素材执行为主，低自主、强 KPI"])
    if has_growth and not has_growth_exec and (has_ai or has_growth_own) and not has_product_title:
        return ("数据驱动用户增长（策略·产品向）", "A", confidence, ["策略/数据/AI 驱动的用户增长（产品向）"])

    if has_edu and (has_ai or has_product_title):
        return ("语言学习/教育产品", "A", confidence, ["教育/语言学习产品方向"])

    if has_product_title:
        if has_content and not (has_ops_signal or has_ownership):
            return ("内容向（产品标题但内容为主）", "C", "low", ["标题含产品但 JD 偏内容生产"])
        if "产品运营" in title or ("运营" in title and "产品" in title):
            if has_ai:
                return ("AI 产品运营（产品侧）", "A", confidence, ["AI 产品运营，产品侧信号"])
            return ("产品运营/用户增长", "B", confidence, ["产品运营，AI 信号弱"])
        if "产品助理" in title or "助理" in title:
            return ("AI 产品助理/初级 PM", "A", confidence, ["产品助理/初级产品入口"])
        if "产品经理" in title or "pm" in title or "策略产品" in title:
            if has_ai:
                return ("AI 产品经理", "A", confidence, ["AI 产品经理方向"])
            return ("泛产品经理", "C", confidence, ["泛产品经理，缺少 AI 信号"])
        return ("产品向（待确认）", "B", confidence, ["产品相关标题"])

    if _any(text, lex("growth_gtm")):
        return ("商业化/GTM/增长", "B", confidence, ["商业化/增长探索"])

    if _any(text, lex("backoffice")):
        if has_ai:
            return ("数据/中台/B 端（含 AI 面）", "B", confidence, ["B 端/数据产品但有 AI 面"])
        return ("B 端后台产品", "C", confidence, ["纯 B 端/中台/后台"])

    if has_edu:
        return ("语言学习/教育（弱信号）", "B", confidence, ["教育/语言但产品信号弱"])

    return ("信息不足/待确认", "unknown", "low", ["方向信号不足"])


# --------------------------------------------------------------------------- #
# Hard filters (block approval candidacy)
# --------------------------------------------------------------------------- #
def detail_report_hard_reasons(row, root=None):
    reasons: list[str] = []
    risk_terms = ["抗压", "高压", "996", "大小周", "随时响应", "结果导向", "业绩指标",
                  "销售目标", "quota", "revenue", "5-10年", "10年以上"]
    for p in report_paths(row, root):
        try:
            text = p.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        risk_section = text
        m = re.search(r"## risk evidence from jd\n\n(.*?)(?:\n## |\Z)", text, flags=re.S)
        if m and "no explicit hard-filter risk captured" not in m.group(1):
            risk_section = m.group(1)
        hits = [t for t in risk_terms if t.lower() in risk_section]
        if hits:
            reasons.append(f"详情报告风险：{p.name} / " + "、".join(hits[:4]))
    return reasons


def company_quality_flags(facts, jd_text="", company="", today_year=None):
    """Deterministic company red lines (run after browser/cdp_company.mjs)."""
    facts = facts or {}
    text = f"{jd_text or ''} {company or ''}"
    cq = cfg("company_quality", default={}) or {}
    reasons: list[str] = []

    founded = str(facts.get("founded", "") or "")
    m = re.search(r"(\d{4})", founded)
    if m:
        yr = int(m.group(1))
        cur = today_year or datetime.date.today().year
        if cq.get("reject_founded_this_year", True) and yr >= cur:
            reasons.append(f"公司当年新成立({yr})")
        elif cur - yr < int(cq.get("reject_founded_within_years", 2)):
            reasons.append(f"公司过新(成立{yr})")

    size = str(facts.get("size", "") or "")
    funding = str(facts.get("funding", "") or "")
    if cq.get("reject_micro_early", True) and "0-20人" in size and (
        funding in ("", "未融资", "天使轮") or "天使" in funding
    ):
        reasons.append(f"微型早期初创(0-20人/{funding or '融资不明'})")

    sched = [t for t in (cq.get("work_schedule_red_terms") or []) if t in text]
    if sched:
        reasons.append("工时红线：" + "、".join(sched[:3]))
    if any(t in text for t in (cq.get("call_center_terms") or [])):
        reasons.append("呼叫中心/电销类")
    if any(t in text for t in (cq.get("outsource_terms") or [])) or \
       any(c in (company or "") for c in (cq.get("outsource_companies") or [])):
        reasons.append("外包/驻场/派遣体系")
    return reasons


def hard_filter_reasons(row, root=None):
    text = scoring_text(row, root)
    title = str(row.get("title", ""))
    company = str(row.get("company", ""))
    hf = cfg("hard_filters", default={}) or {}
    reasons: list[str] = []

    weak_role_hits = [t for t in lex("weak_role") if t in text]
    workload_hits = [t for t in lex("workload_risk") if t in text]
    pm_strict_hits = [t for t in lex("traditional_pm_strict") if t in text]
    hidden_hits = [t for t in lex("hidden_jd") if t in text]
    backoffice_hits = [t for t in lex("backoffice") if t in text]
    low_asset_hits = [t for t in lex("low_asset") if t in text]
    has_content = _any(text, lex("content_exec"))
    has_community = _any(text, lex("community_ops"))
    tool_hits = sum(1 for t in lex("tool_eval_ownership") if t in text)
    prod_hits = sum(1 for t in lex("content_production") if t in text)
    has_ownership = tool_hits >= 2 and tool_hits >= prod_hits
    has_product_title = _any(title.lower(), lex("product_title"))
    surface_ok = has_approval_surface(text)
    req = required_years(row, text)

    if hf.get("reject_internship_parttime", True) and is_intern_or_parttime(row, text):
        reasons.append("实习/兼职/短期项目")
    if hf.get("reject_major_mismatch", True) and has_major_mismatch(text):
        reasons.append("专业背景要求不匹配")
    if weak_role_hits and not has_product_title and not has_ownership:
        reasons.append("弱匹配/默认排除岗位：" + "、".join(weak_role_hits[:3]))
    if hidden_hits:
        reasons.append("详情/JD 信息不完整：" + "、".join(hidden_hits[:2]))
    hard_years = int(hf.get("experience_hard_max_years", 3))
    if req is not None and req >= hard_years:
        reasons.append(f"经验要求 ≥{req} 年，超出范围")
    if workload_hits:
        reasons.append("工作强度或业绩风险：" + "、".join(workload_hits[:3]))
    if pm_strict_hits and not surface_ok:
        reasons.append("传统 PM 工具/流程为主：" + "、".join(pm_strict_hits[:4]))
    if backoffice_hits and not surface_ok:
        reasons.append("偏 B 端/中台/后台且缺少用户/内容/AI 面")
    if low_asset_hits and not surface_ok:
        reasons.append("可迁移资产弱：" + "、".join(low_asset_hits[:3]))
    if has_content and not has_ownership and not has_product_title:
        reasons.append("内容生产/运营为主，无产品或工具 ownership（默认跳过）")
    if has_community and not has_product_title:
        reasons.append("社区/社群运营为主的执行岗（默认跳过）")
    if hf.get("reject_higher_ed_and_gov", True) and is_higher_ed_or_gov(company, text):
        reasons.append("高校/国企/央企/事业单位")
    if hf.get("reject_early_stage", True) and is_early_stage(text):
        reasons.append("早期初创（天使/种子/Pre-A/未融资）造血能力存疑")
    floor = salary_floor_of(row)
    floor_min = int(hf.get("salary_floor_min_k", 8))
    if floor is not None and floor < floor_min:
        reasons.append(f"薪资过低（下限 {floor}K）")
    if hf.get("reject_company_opacity", True) and (
        not company or company.startswith("某") or "某" in company or "..." in company
    ):
        reasons.append("公司信息不完整")

    reasons.extend(detail_report_hard_reasons(row, root))
    return reasons


# --------------------------------------------------------------------------- #
# Band scoring
# --------------------------------------------------------------------------- #
def score_job(row, root=None):
    text = scoring_text(row, root)
    title = str(row.get("title", ""))
    city = str(row.get("city", ""))
    company = str(row.get("company", ""))
    salary = str(row.get("salary", ""))

    sc = cfg("scoring", default={}) or {}
    tier_base = sc.get("tier_base") or {"A": 4.0, "B": 3.5, "C": 2.9, "D": 2.0, "unknown": 3.2}
    mods = sc.get("modifiers") or {}
    lo, hi = (sc.get("modifier_bounds") or [-0.8, 0.8])

    archetype, tier, confidence, _ = classify_archetype(row, text)
    score = float(tier_base.get(tier, 3.2))
    positives = [f"方向判定：{archetype}（Tier {tier}）"]
    cautions: list[str] = []

    strong_hits = [t for t in lex("strong_target") if t in text]
    secondary_hits = [t for t in lex("secondary_target") if t in text]
    junior_hits = [t for t in lex("junior_friendly") if t in text]
    visible_hits = sorted({t for t in lex("visible_work") if t in text})
    ai_tool_hits = [t for t in lex("ai_tool_practice") if t in text]
    has_ops_signal = _any(text, lex("product_ops_signal"))

    mod = 0.0
    if strong_hits:
        positives.append("方向贴合：" + "、".join(strong_hits[:4]))
    if secondary_hits:
        positives.append("相关标签：" + "、".join(secondary_hits[:3]))
    if junior_hits:
        mod += mods.get("junior_friendly", 0.3)
        positives.append("经验入口友好：" + "、".join(junior_hits[:3]))
    if len(visible_hits) >= 2:
        mod += mods.get("visible_work_2plus", 0.25)
        positives.append("有可见产出/反馈：" + "、".join(visible_hits[:3]))
    elif visible_hits:
        mod += mods.get("visible_work_1", 0.1)
        positives.append("有可见产出/反馈：" + "、".join(visible_hits[:2]))
    if ai_tool_hits:
        mod += mods.get("ai_tool_in_practice", 0.2)
        positives.append("实践用 AI 工具：" + "、".join(ai_tool_hits[:3]))
    if has_ops_signal and tier in {"A", "B"}:
        mod += mods.get("ops_signal", 0.1)

    cities = cfg("search", "cities", default=["上海"]) or ["上海"]
    primary = cities[0] if cities else ""
    secondary = cities[1] if len(cities) > 1 else ""
    if primary and primary in city:
        mod += mods.get("city_primary", 0.2)
        positives.append(f"城市匹配{primary}")
    elif secondary and secondary in city:
        mod += mods.get("city_secondary", 0.1)
        positives.append(f"城市匹配{secondary}（次优先）")
    elif city and "远程" not in text and "居家" not in text:
        mod += mods.get("city_other", -0.4)
        cautions.append(f"非首选城市：{city}")

    floor = parse_salary_floor(salary)
    if floor is not None:
        if floor >= int(sc.get("salary_high_floor_k", 15)):
            mod += mods.get("salary_high", 0.1)
        elif floor < int(sc.get("salary_low_floor_k", 10)):
            mod += mods.get("salary_low", -0.2)
            cautions.append("薪资下限偏低")

    mod = max(lo, min(hi, mod))
    score += mod

    # hard caps (JD-aware)
    caps: list[float] = []
    req = required_years(row, text)
    strong_ai_edu = _any(text, ("ai", "aigc", "agent", "大模型", "教育", "语言学习")) and tier in {"A", "B"}
    if req is not None:
        if req >= 10:
            caps.append(3.0); cautions.append("经验要求过高：约 10 年+")
        elif req >= 5:
            caps.append(3.1); cautions.append(f"经验要求明显偏高：约 {req} 年")
        elif req >= 3:
            caps.append(3.4 if strong_ai_edu else 3.2); cautions.append(f"经验要求偏高：约 {req} 年")
        elif req == 2:
            caps.append(3.9); cautions.append("经验要求 2 年（stretch，可冲）")

    if "产品经理" in title and "ai" not in title.lower() and not junior_hits:
        caps.append(3.4); cautions.append("泛产品经理信号不足")
    if is_intern_or_parttime(row, text):
        caps.append(2.4); cautions.append("非全职/实习短期岗位")
    if has_major_mismatch(text):
        caps.append(3.0); cautions.append("专业背景要求不匹配")
    if _any(text, lex("hidden_jd")):
        caps.append(3.1); cautions.append("JD 信息不完整/未登录隐藏")
    if _any(text, lex("weak_role")) and not _any(title.lower(), lex("product_title")) \
       and not _any(text, lex("tool_eval_ownership")):
        caps.append(2.5); cautions.append("弱匹配/销售服务类")
    if _any(text, lex("workload_risk")) and _any(text, ("销售", "业绩", "quota", "revenue")):
        caps.append(2.5); cautions.append("强业绩/quota 风险")
    if _any(text, lex("traditional_pm_strict")) and not _any(text, (
        "ai", "aigc", "agent", "大模型", "prompt", "提示词", "内容增长", "产品运营",
        "用户增长", "增长运营", "ai coding", "自动化工作流", "原型验证",
    )):
        caps.append(3.2); cautions.append("传统 PM 设计工具为主")
    if tier == "C":
        caps.append(3.2)
    if tier == "D":
        caps.append(2.4)
    if _any(text, lex("backoffice")) and not _any(text, lex("exception")):
        caps.append(3.0); cautions.append("偏 B 端/中台/后台，缺少用户/内容/AI 信号")
    if not company or company.startswith("某") or "某" in company or "..." in company:
        caps.append(3.0); cautions.append("公司信息不完整")
    if is_higher_ed_or_gov(company, text):
        caps.append(2.9); cautions.append("高校/国企/央企/事业单位")
    if is_early_stage(text):
        caps.append(3.0); cautions.append("早期初创/造血能力存疑")
    floor_min = int(cfg("hard_filters", "salary_floor_min_k", default=8))
    if floor is not None and floor < floor_min:
        caps.append(2.6); cautions.append(f"薪资过低（下限 {floor}K）")
    elif floor is not None and floor < int(sc.get("salary_low_floor_k", 10)):
        cautions.append(f"薪资偏低（下限 {floor}K）")
    if city and primary not in city and (not secondary or secondary not in city) \
       and "远程" not in text and "居家" not in text:
        caps.append(3.4)

    if caps:
        score = min(score, min(caps))

    # confidence / JD-evidence gate
    jd_evidenced = bool(
        re.search(r"report=", str(row.get("notes", "")).lower())
        or any(k in text for k in ("职位描述", "岗位职责", "任职", "职位要求", "工作内容", "工作职责"))
    )
    if not jd_evidenced:
        cap = float(sc.get("no_jd_evidence_cap", 4.2))
        score = min(score, cap)
        cautions.append(f"仅列表卡证据，未抓 JD（封顶 {cap}）")
    if confidence == "low":
        cap = float(sc.get("low_confidence_cap", 3.4))
        score = min(score, cap)
        cautions.append("分类信号冲突/不足，建议人工判断")

    score = max(1.0, min(5.0, round(score, 1)))
    return score, positives, cautions


def score_text(score: float) -> str:
    return f"{score:.1f}/5"


def decision_label(score: float) -> str:
    if score >= 4.3:
        return "strong"
    if score >= 3.6:
        return "good"
    if score >= 3.2:
        return "mixed"
    return "weak"


def decision_action(score: float) -> str:
    return {
        "strong": "优先审批，可定制招呼语",
        "good": "可以审批，注意风险点",
        "mixed": "谨慎保留，需要人工判断",
        "weak": "默认跳过，除非手动覆盖",
    }[decision_label(score)]


def summarize_fit(row, root=None):
    score, positives, cautions = score_job(row, root)
    parts: list[str] = []
    if positives:
        parts.append("加分：" + "；".join(positives[:3]))
    if cautions:
        parts.append("风险：" + "；".join(cautions[:3]))
    if not parts:
        parts.append("信息完整，待人工判断")
    return score_text(score), " | ".join(parts)
