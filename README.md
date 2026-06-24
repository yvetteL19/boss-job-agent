# boss-job-agent

> 一个**配置驱动、人在环、永不自动发送**的 BOSS 直聘求职 AI agent。
> 它替你做机器的活——发现岗位、读 JD、按你的画像打分、起草招呼语、追踪漏斗——
> 把「发不发、投不投」的判断权完整留给你。
>
> A config-driven, human-in-the-loop job-search agent for BOSS Zhipin (直聘).
> It automates discovery, JD reading, archetype-band scoring, greeting drafts and
> funnel tracking. It **never** auto-sends or auto-applies. You decide.

### 👉 新手从这里开始：[ONBOARDING.md](ONBOARDING.md)（5 分钟，3 步上手）

下面是完整说明；只想跑起来的话看上面那篇就够。

**依赖与边界（先说清楚）**
- **不需要 Obsidian**：数据层是纯 `CSV/JSON`，生成的 `Dashboard.md` 等是普通 Markdown，
  任何编辑器或笔记软件都能打开（包括 Obsidian，但并不依赖它）。
- **不调用任何 MCP / LLM API**：和 BOSS 的交互全走 `browser/` 的 Node CDP 脚本；「LLM 读 JD
  判断」这步由**你当前会话的 LLM**（如 Claude Code）完成，代码不内置 key、无费用。
- 只需 **Python 3.10+** 和 **Node 18+**。

---

## 为什么是这样设计的（先看这个）

市面上的「求职机器人」大多在做一件危险的事：**自动批量打招呼/投递**。在 BOSS 直聘上这会
触发账号风控（封号），而且把你最该亲自把关的一步（要不要联系这家公司）交给了机器。

这个项目反其道而行，把求职里最该你亲自把关的判断权留在你手里，固化成三条铁律：

1. **发送永远手动。** AI 只做不改变平台状态的活：发现、读 JD、打分、起草、追踪。
2. **打分不是关键词加总，而是「先归类、再按档给分」**——先判断这个岗位「是什么」
   （archetype → 档位），再在档内用证据微调，关键词只当硬性安全网；真正的匹配判断交给
   读完 JD 正文的 LLM。
3. **机器活一次跑完，你只介入一次。** 一条命令把搜索→读 JD→公司体检→硬门全跑完，
   只把「需要人判断」的幸存者交给你，做结论先行的 15 秒决策。

详见 [ARCHITECTURE.md](ARCHITECTURE.md) 和 [docs/SAFETY.md](docs/SAFETY.md)。

---

## 它能做什么

| 阶段 | agent 做的 | 你做的 |
|---|---|---|
| 发现 | 用隔离浏览器搜索关键词、抓列表卡入台账 | 给方向（关键词/城市） |
| 筛选 | 规则预筛 → 读 JD 正文 → 公司工商体检 → 确定性硬门 | — |
| 判断 | LLM 逐条读 JD，对照你的画像给分 + 理由 + 风险 | 看结论先行卡，`approve` / `skip` |
| 起草 | 按 archetype 生成人话招呼语（无破折号、不复述 JD） | 改成你的话 |
| 发送 | 在隔离浏览器开好标签 | **手动**逐个打招呼粘贴发送 |
| 追踪 | 维护台账、漏斗、周报 | 报「发了哪些」 |

---

## 架构总览

```
                    config/profile.yaml   ← 唯一的个性化来源（你的画像/偏好/词表/招呼语）
                            │
   隔离 Chrome (CDP 9222)   │  browser/*.mjs（搜索/读JD/公司体检/开标签，永不碰你日常 Chrome）
            │               ▼
   ┌──────────────── agent.discover（一次跑完的编排器）─────────────────┐
   │  search → ingest → 规则预筛 → 读 JD → 公司体检 → 确定性硬门          │
   └───────────────────────────────┬───────────────────────────────────┘
                                    ▼
                        data/_batch_packet.json（幸存者）
                                    │
        agent.llm_eval（LLM 读 JD 判断，写回台账）  ←─ 你/会话里的 LLM
                                    ▼
   data/applications.csv（台账 = 真相源）──► agent.render_decision_batch（结论先行卡）
                                    │                       │
                          agent.decide（approve/skip）       ▼  你看卡做决定
                                    ▼
        agent.greetings（招呼语草稿） ──► agent.render_send_queue ──► browser/cdp_open.mjs
                                                                          │
                                                              你在隔离浏览器手动发送
                                    │
                        agent.render_dashboard / agent.weekly_review（漏斗 + 复盘）
```

数据分两层（[docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md)）：**用户层**（`config/profile.yaml`、
`data/applications.csv` 台账，全部 gitignored，永不进仓库）与**系统层**（`agent/`、`browser/`
脚本逻辑，可随系统升级而改）。个性化只进配置，不进代码。

---

## 快速开始

### 0. 依赖

- Python 3.10+，`pip install -r requirements.txt`（只需 PyYAML）
- Node 18+（自带 `fetch`/`WebSocket`，用于 CDP 浏览器脚本）

### 1. 写你的画像

```bash
cp config/profile.example.yaml config/profile.yaml
# 编辑 config/profile.yaml：城市、关键词、硬过滤、招呼语、词表。这是唯一要改的文件。
```

### 2. 先离线跑通引擎（不连 BOSS，用合成数据）

```bash
cp examples/sample_search_page.json data/current_page.json
./jobagent ingest        # 8 个合成岗位入台账并打分
./jobagent dashboard     # 生成 Dashboard.md + Approval Queue.md
./jobagent doctor        # 体检
```

打开 `Approval Queue.md` 看打分与分档是否符合预期，调 `config/profile.yaml` 再重跑。

### 3. 接真实 BOSS（隔离浏览器）

> ⚠️ 这步会向 BOSS 发起真实访问。首次先用较小的 `--top`（如 6）小批量试跑，遇到验证码或
> 风控提示立即停（见 [docs/SAFETY.md](docs/SAFETY.md)）。

```bash
# 一次性安装 Chrome for Testing
npx @puppeteer/browsers install chrome@stable
# 启动隔离浏览器（端口 9222），扫码登录 BOSS 一次，后台挂着
CHROME_BIN="/path/to/chrome" bash browser/launch_chrome.sh

# 一条命令跑完所有机器活
./jobagent discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 12
```

然后：LLM 读 JD 判断（写 `data/llm_evals.json` → `./jobagent eval`）→
`./jobagent cards` 看卡 → `./jobagent decide --approve 1,3` → `./jobagent greet` 起草 →
`./jobagent send` → `./jobagent open` 开标签 → **你手动发送**。

完整 SOP 见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。

---

## 命令速查（统一 CLI）

不带参数运行 `./jobagent` 会列出所有命令；每个命令支持 `-h`。
（也可以等价地用 `python3 -m agent <命令>`。）

| 命令 | 作用 |
|---|---|
| `./jobagent discover --keywords ... --cities ... --top 12` | 一次跑完发现→硬门，产出幸存者 packet |
| `./jobagent discover --from-cache --top 12` | 跳过网络，仅用已抓数据重跑硬门 |
| `./jobagent ingest` | 把 `data/current_page.json` 的列表卡入台账 |
| `./jobagent eval` | 把 `data/llm_evals.json` 的 LLM 判断写回台账 |
| `./jobagent cards` | 生成结论先行决策卡 `Decision Batch.md` |
| `./jobagent decide --approve 1,3 --skip 2` | 按编号审批 |
| `./jobagent greet` | 生成招呼语草稿到 `data/greetings.json` |
| `./jobagent send` | 生成发送清单 + 开页 URL 列表 |
| `./jobagent open` | 在隔离浏览器把 approved 岗位开成标签（仍手动发送） |
| `./jobagent dashboard` | 生成 `Dashboard.md` + `Approval Queue.md` |
| `./jobagent review` | 漏斗 + 转化周报 |
| `./jobagent doctor` | 跑批前体检 |

---

## 免责声明

- 本项目用于**辅助个人求职**：自动化仅限发现/阅读/打分/起草/追踪。它**不**自动发送、
  不自动投递、不绕过验证码或风控。请遵守 BOSS 直聘的服务条款，控制频率，风险自负。
- 仓库内不含任何真实个人简历、偏好或投递记录；`config/profile.yaml` 与 `data/` 全部
  gitignored。示例画像是合成的通用 AI 产品/增长求职者。

## License & 设计渊源

MIT（见 [LICENSE](LICENSE)）。数据契约 / 规范化状态 / 结果模式分析的思路受 MIT 许可的
[`santifer/career-ops`](https://github.com/santifer/career-ops) 启发；本项目是面向 BOSS
直聘的独立实现，未直接复用其代码。
