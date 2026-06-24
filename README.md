# 🎯 boss-job-agent（BOSS 直聘求职助手）

> 一个替你跑腿、但把决定权留给你的 BOSS 直聘求职 agent：它发现岗位、读 JD、按你的标准打分、
> 起草招呼语、追踪进度——**发送这一步，永远由你亲手按下**。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Node](https://img.shields.io/badge/Node-18%2B-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![平台](https://img.shields.io/badge/平台-BOSS%20直聘-success)

求职最累的不是投递，是每天在几十个 JD 里重复判断「这家值不值得聊」。boss-job-agent 把这些机器
能做的活——搜索、读 JD 正文、查公司工商信息、按你的画像打分排雷——压进一条命令，只把真正需要你
判断的少数候选，做成结论先行的卡片递到你面前。你花 15 秒决定 approve 还是 skip，剩下的它接着干。
它不会替你发招呼，也不会偷偷投递——那是你的事，也是你账号安全的底线。

> *An AI agent that finds, reads, scores and tracks BOSS Zhipin (直聘) jobs against
> your own profile, and drafts your openers — while you keep the send button.*

**新手直接看 → [ONBOARDING.md](ONBOARDING.md)（5 分钟，3 步跑起来）**

---

## ✨ 功能特性

- **一条命令跑完所有机器活**——搜索 → 读 JD 正文 → 查公司工商信息 → 硬性排雷，一次完成，
  只把需要你判断的候选交到面前。
- **先归类、再打分的匹配引擎**——先判断岗位「是什么」（archetype → 档位），再在档内按证据
  微调；标题党的「AI」刷不出高分。
- **读完 JD 的智能判断**——由你会话里的 LLM 逐条读 JD 正文，对照你的画像给出分数、理由和风险，
  关键词只当安全网。
- **公司工商体检**——成立年份、规模、融资阶段、工时红线、外包/呼叫中心，发现阶段就排雷，
  不等到发招呼才踩坑。
- **结论先行的决策卡**——每张卡先抛结论，再附公司体检和唯一风险，你 15 秒决定 approve / skip。
- **人话招呼语草稿**——按岗位方向生成，落点回到你的优势，无破折号、不复述 JD，复制即用。
- **发送键永远在你手里**——agent 帮你把岗位开成标签、备好招呼语，最后一步由你亲手发送，
  稳稳避开账号风控。
- **隔离浏览器，不打扰日常**——专用浏览器实例驱动、节奏拟人，绝不碰你日常用的浏览器。
- **全程留痕的台账**——每个岗位从发现到面试的状态都记在本地 CSV，配套漏斗看板和周报，
  策略可复盘。
- **一个 YAML 定义你自己**——城市、关键词、硬过滤、招呼语全在 `config/profile.yaml`，
  换个人改一个文件就行。

---

## 🔄 工作原理

机器把活一次干完，你只在「该你判断」的地方介入一次。

```
        config/profile.yaml  ← 你的画像（城市/关键词/硬过滤/招呼语）
                 │
   隔离浏览器 ◄───┤  browser/*.mjs（搜索 · 读 JD · 公司体检 · 开标签）
                 ▼
   ┌──── jobagent discover（一次跑完）──────────────────────┐
   │  搜索 → 入台账 → 规则预筛 → 读 JD → 公司体检 → 硬门排雷   │
   └──────────────────────────┬─────────────────────────────┘
                              ▼
   会话里的 LLM 读 JD 判断 ─► jobagent eval ─► data/applications.csv（台账=真相源）
                                                     │
                              jobagent cards ─► 结论先行决策卡  ──►  你 approve / skip
                                                     │
   jobagent greet（招呼语） ─► jobagent send ─► jobagent open（开标签）─► 你手动发送
                                                     │
                       jobagent dashboard / review（看板 · 周报）
```

- **你负责**：给方向（关键词/城市）、按编号 approve/skip、在隔离浏览器里手动发招呼。
- **agent 负责**：发现 → 读 JD → 核公司 → 打分 → 起草 → 追踪，并维护台账与各视图。
- 北极星是 **offer，不是发够 10 个冷招呼**：质量优先，真漏斗指标是回复率/面试率。

---

## 🚀 快速开始

**环境要求：** Python 3.10+、Node 18+。「LLM 读 JD」用你当前会话的模型完成，无需 API key。

```bash
git clone https://github.com/yvetteL19/boss-job-agent.git
cd boss-job-agent
pip install -r requirements.txt
cp config/profile.example.yaml config/profile.yaml   # 改成你的画像，仅此一个文件
```

**先离线试跑**（用合成数据，零风险地把引擎玩熟）：

```bash
cp examples/sample_search_page.json data/current_page.json
./jobagent ingest        # 8 个示例岗位入台账并打分
./jobagent dashboard     # 生成 Dashboard.md + Approval Queue.md
```

打开 `Approval Queue.md` 看打分与分档是否符合你的预期，回去调 `config/profile.yaml` 再重跑。

**接真实 BOSS**（隔离浏览器）：

```bash
npx @puppeteer/browsers install chrome@stable          # 装一次
CHROME_BIN="/上一步打印的chrome路径" bash browser/launch_chrome.sh   # 扫码登录一次，后台挂着
./jobagent discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 6
```

> ⚠️ `discover` 会向 BOSS 发起真实访问。首次先用较小的 `--top` 小批量试跑，遇到验证码或风控
> 提示立即停（见 [docs/SAFETY.md](docs/SAFETY.md)）。

完整每日流程见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。

---

## 🧰 命令速查

运行 `./jobagent` 不带参数会列出全部命令，每个命令支持 `-h` 查看参数。

| 命令 | 作用 |
| :--- | :--- |
| `jobagent discover --keywords … --cities … --top N` | 一次跑完发现 → 硬门，产出待审候选 |
| `jobagent ingest` | 把搜索到的列表卡入台账 |
| `jobagent eval` | 把 LLM 的 JD 判断写回台账 |
| `jobagent cards` | 生成结论先行决策卡 `Decision Batch.md` |
| `jobagent decide --approve 1,3 --skip 2` | 按编号审批 |
| `jobagent greet` | 生成招呼语草稿到 `data/greetings.json` |
| `jobagent send` | 生成手动发送清单 `Send Queue.md` |
| `jobagent open` | 在隔离浏览器把已批准岗位开成标签（仍手动发送） |
| `jobagent dashboard` | 生成 `Dashboard.md` + `Approval Queue.md` |
| `jobagent review` | 漏斗 + 转化周报 |
| `jobagent doctor` | 跑批前体检 |

---

## ⚙️ 你的画像（唯一要改的文件）

`config/profile.yaml` 是整个 agent 的个性化来源，脚本只读它、绝不写死偏好：

```yaml
search:
  cities: [上海, 杭州]
  keywords: [用户增长, AI 产品运营, AI 产品助理]
hard_filters:
  salary_floor_min_k: 8          # 薪资下限低于这个数直接排除
  experience_hard_max_years: 3   # 要求年限 ≥ 这个数则排除（junior 友好除外）
  reject_internship_parttime: true
greetings:
  intro: "你好，我是 26 届市场营销硕士"
  # 招呼语模板，换成你自己的故事 …
```

它在 `.gitignore` 里，永远不会被提交。完整字段见 `config/profile.example.yaml` 内的注释。

---

## 🧱 架构设计

引擎与流程与平台无关，BOSS 特有的部分只集中在 `browser/*.mjs`。

| 模块 | 职责 |
| :--- | :--- |
| `agent/rules.py` | 匹配引擎：archetype 归类 + 档位打分 + 硬过滤（核心） |
| `agent/config.py` | 读取 `profile.yaml`、解析路径与词表 |
| `agent/ledger.py` | 台账 `data/applications.csv` 读写与去重 |
| `agent/discover.py` | 一次跑完的编排器（搜索→读JD→公司体检→硬门） |
| `agent/llm_eval.py` | 把会话 LLM 的 JD 判断写回台账 |
| `agent/decide.py` | 按编号 approve / skip |
| `agent/greetings.py` | 配置模板生成招呼语 |
| `agent/render_*.py` | 决策卡 / 发送清单 / 看板渲染 |
| `agent/weekly_review.py` | 漏斗与转化周报 |
| `browser/*.mjs` | 隔离浏览器的搜索 / 读 JD / 公司体检 / 开标签 |

设计细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。

---

## 📁 项目结构

```
boss-job-agent/
├── jobagent                      # 统一 CLI 入口
├── agent/                        # Python 引擎（打分 · 台账 · 编排 · 渲染）
├── browser/                      # 隔离浏览器 CDP 脚本 + 启动脚本
├── config/
│   └── profile.example.yaml      # 画像模板（复制成 profile.yaml）
├── docs/                         # WORKFLOW · SCREENING_RUBRIC · SAFETY · DATA_CONTRACT
├── examples/                     # 合成示例数据（离线试跑用）
├── templates/                    # 岗位笔记模板
├── data/                         # 你的台账与缓存（本地，不进仓库）
├── README.md · ARCHITECTURE.md · ONBOARDING.md
```

---

## 🔒 安全与边界

- **发送永远手动。** 自动化仅限发现、阅读、打分、起草、追踪；发招呼、投递、过验证码这些
  会改变平台状态的动作，都由你亲手完成——这既是产品原则，也是账号安全的底线。
- **隔离浏览器、拟人节奏。** 所有访问走专用浏览器实例，多秒等待 + 随机抖动，遇风控即停。
- **数据只在本地。** 你的画像与台账保存在本机，仓库里不含任何真实简历、偏好或投递记录。

详见 [docs/SAFETY.md](docs/SAFETY.md)。

---

## ⚖️ 免责声明 & License

辅助**个人**求职使用，请遵守 BOSS 直聘服务条款、控制频率、风险自负。
MIT License（见 [LICENSE](LICENSE)）；数据契约与结果复盘的思路受 MIT 许可的
[`santifer/career-ops`](https://github.com/santifer/career-ops) 启发，本项目为面向 BOSS 直聘的
独立实现。

<p align="center">把跑腿交给 agent，把判断留给自己。</p>
