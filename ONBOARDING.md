# 上手指南（5 分钟）

> 不需要 Obsidian，不需要 MCP，不需要任何 API key。
> 只要 Python 3.10+ 和 Node 18+。

## 它是什么（一句话）

一个帮你在 BOSS 直聘求职的助手：**它发现岗位、读 JD、按你的标准打分、起草招呼语、记录进度；
但永远不替你发送**。你只做两件事——给方向、按编号 approve/skip，最后手动发招呼。

---

## 第 1 步：装好 + 写画像

```bash
git clone https://github.com/yvetteL19/boss-job-agent
cd boss-job-agent
pip install -r requirements.txt        # 只装一个 PyYAML

cp config/profile.example.yaml config/profile.yaml
```

打开 `config/profile.yaml`，改这几样就够开始：
- `search.cities` / `search.keywords` —— 你想要的城市和搜索词
- `hard_filters` —— 你的硬性排除（薪资下限、经验年限、是否拒实习等）
- `greetings` —— 招呼语模板，换成你自己的故事

> 这是**唯一**要改的文件。它在 `.gitignore` 里，不会被提交。

---

## 第 2 步：先离线跑一遍（不连 BOSS，用假数据）

```bash
cp examples/sample_search_page.json data/current_page.json
./jobagent ingest        # 8 个假岗位入台账并打分
./jobagent dashboard     # 生成 Dashboard.md 和 Approval Queue.md
```

打开 `Approval Queue.md`（普通 Markdown，任何编辑器都能看）。看打分和分档对不对，
不满意就回去调 `config/profile.yaml` 再 `./jobagent ingest` 重跑。**这一步零风险，先玩熟。**

---

## 第 3 步：接真实 BOSS

> ⚠️ 这一步的命令会向 BOSS 发起真实访问。第一次先用较小的 `--top`（比如 6）小批量试跑，
> 确认节奏正常再放大；遇到验证码、风控提示或登录异常**立即停下**，等冷却。详见
> [docs/SAFETY.md](docs/SAFETY.md)。

```bash
# 1) 装一次隔离浏览器（和你日常 Chrome 完全分开，防止账号风控）
npx @puppeteer/browsers install chrome@stable

# 2) 启动它，扫码登录 BOSS 一次，然后挂后台别关
CHROME_BIN="/上面打印的chrome路径" bash browser/launch_chrome.sh

# 3) 一条命令跑完所有机器活
./jobagent discover --keywords 用户增长,AI产品运营 --cities 上海,杭州 --top 12
```

跑完后是「人审 + 手动发」环节：

```bash
./jobagent cards         # 看结论先行的决策卡 Decision Batch.md
./jobagent decide --approve 1,3 --skip 2
./jobagent greet         # 起草招呼语（去 data/greetings.json 改成你的话）
./jobagent send          # 生成发送清单 Send Queue.md
./jobagent open          # 在隔离浏览器把这些岗位开成标签
# → 你逐个手动打招呼、粘贴、发送。发送永远是你点的，不是脚本。
```

---

## 常见疑问

**「LLM 读 JD 判断」这步谁来做？**
你正在用的那个 LLM（比如 Claude Code / ChatGPT）。把 `discover` 产出的 `data/_batch_packet.json`
丢给它，让它对照你的画像逐条判断，按 `agent/llm_eval.py` 顶部的格式写成 `data/llm_evals.json`，
再 `./jobagent eval` 写回台账。**代码本身不调任何 LLM API**，所以没有 key、没有费用。

**用了 MCP 吗？**
没有。所有和 BOSS 的交互都走 `browser/` 里的 Node CDP 脚本（驱动那个隔离浏览器），不依赖任何
MCP 服务。

**所有命令都不记得怎么办？**
`./jobagent` 不带参数会列出全部命令；每个命令 `-h` 看自己的参数。

**完整工作流和安全说明** → [docs/WORKFLOW.md](docs/WORKFLOW.md) ·
[docs/SAFETY.md](docs/SAFETY.md)
