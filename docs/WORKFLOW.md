# Workflow (daily SOP)

The operating model is **one machine pass + one human review**. The machine
front-loads everything deterministic; you engage once on real candidates.

> Commands below are written as `python3 -m agent.<module>`. The short form
> `./jobagent <command>` is equivalent (run `./jobagent` to list commands).

## Roles

- **You**: give direction (keywords/cities); approve/skip; send greetings
  manually in the isolated browser; read the weekly review.
- **Agent**: discover → read JD → vet company → score → draft greeting → track.
  Maintains `data/applications.csv` (truth source) and the rendered views.

## The pipeline

```text
[machine, one command]
  python3 -m agent.discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 12
    internal: search (cdp_search) → ingest → rule pre-filter (gate 1) → read JD
              (cdp_detail) → company health (cdp_company) → deterministic gate
              (gate 1 + gate 2 company red lines)
    output: data/_batch_packet.json = survivors (JD + company facts + no red flags)

[judgment]
  In-session LLM reads each survivor's JD, judges fit vs. your profile, writes
  data/llm_evals.json → python3 -m agent.llm_eval (writes score/archetype/verdict
  back to the ledger; hard filters can veto a shortlist)

[render decision cards]
  python3 -m agent.render_decision_batch   → Decision Batch.md
  (conclusion-first cards: verdict + company health + one reason + one risk)

[you decide]
  python3 -m agent.decide --approve 1,3 --skip 2 --reason "..."

[draft + stage send]
  python3 -m agent.greetings --status approved      → data/greetings.json (edit these!)
  python3 -m agent.render_send_queue                → Send Queue.md + _open_urls.json
  node browser/cdp_open.mjs                          → opens tabs in the isolated browser
  → you go top-to-bottom and MANUALLY 打招呼/send each one

[track]
  Tell the agent what you sent → it updates status/applied_at →
  python3 -m agent.render_dashboard
```

## Funnel discipline

A daily target is a number of **communications**, not a number of prepared roles.
Widen the discovery funnel (≈30–40 list cards → ≈20 detail reads → ≈12–18
approval candidates) so you have a real choice set, then approve only what you
would actually be glad to talk to. **Quality over hitting the daily number** —
the north star is offers, measured by reply/interview rate, not send volume.

## Status taxonomy (the ledger)

`discovered` → `shortlisted` → `approved` → `applied` → `replied` → `interview`,
plus terminal/other states: `skipped`, `rejected`, `expired`, `risk_blocked`,
`needs_login`, `unconfirmed`, `already_applied`, `error`.

Rules:
- List-card imports default to `discovered`; promote only after JD evidence and
  hard filters pass.
- A short/failed/hidden JD is under-evidenced; never auto-promote it.
- On any `risk_blocked` / captcha / repeated unknown / login instability —
  **stop the batch** and preserve evidence.

## Weekly review

```bash
python3 -m agent.weekly_review
```

Then reflect: which keywords convert? which archetypes/companies were false
positives? Encode the lessons in `config/profile.yaml` (hard_filters / lexicon /
search keywords) — personalization belongs in config, never in scripts.

## Stop condition

Pause and re-strategize after a planned number of thoughtful applications (e.g.
~100). If reply rates are low, the fix is usually upstream (direction/keywords in
the profile), not "send more".
