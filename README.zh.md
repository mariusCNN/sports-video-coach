<div align="center">

# sports-video-coach

### 你的 AI agent 看你的运动录像，像教练一样给你指导。

[![release](https://img.shields.io/github/v/release/mariusDing/sports-video-coach)](https://github.com/mariusDing/sports-video-coach/releases)
[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)
[![Works with Claude Code and Codex](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex%20%7C%20AGENTS.md-8A2BE2.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)

[English](https://github.com/mariusDing/sports-video-coach/blob/master/README.md) · **中文**

<img alt="作者自己投篮练习的真实运行：原片、agent 的看片复盘在出手后收手定住的地方暂停，然后是教练网页" src="https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/real-session.gif" width="720">

<sub>作者自己投篮练习的一次真实运行：你的视频 → agent 看片复盘 → 你的教练网页。
不用安装就能看完整示例：<a href="https://mariusding.github.io/sports-video-coach/demo/">demo 网页</a>（程序画的练习）。</sub>

</div>

用手机拍下自己：一场比赛、一组练习、一次训练，什么运动都行。
你的编程 agent（Claude Code、Codex、Cursor 等）看带时间戳的帧拼图来复盘，需要时可以再要一张更密的拼图，看清快动作的那一刻。
你拿回一个手机网页：关键片段、每个问题的练习方法和目标、报告的语音版，还有一段讲解视频。
工具在你自己的电脑上跑；agent 看的帧会发给它的模型服务商，和你给它看的其他东西一样。免费，MIT 协议。

## 基准测试：哪个 agent 看运动录像最准

程序画的练习视频，按工具自己画进去的精确真值打分。不用评审模型。

- **新种子榜**（只看静帧，每次运行用一个没公开过的新种子，分数是比盲猜高出的部分取平均，1 = 全对）：
  Codex gpt-6-astra 1.000 · Claude Opus 5.5 0.997（low effort 时 0.778）· Claude Sonnet 5.5 默认 effort 0.419，high 时 0.994（max 超时）·
  本地显卡上的 qwen3-vl 4B 0.000。
  每个 effort 设置只跑了一次；目前所有运行都是作者自己跑的。
- [中文排行榜](https://mariusding.github.io/sports-video-coach/benchmark/zh/#frames-svc-bench-3-fresh) · [自己数一数触球](https://mariusding.github.io/sports-video-coach/benchmark/zh/#count) · [方法和提交方式](https://github.com/mariusDing/sports-video-coach/blob/master/docs/benchmark.md)（英文）
- 一条命令重跑静帧榜：

```bash
sports-video-coach bench run --agent claude --suite svc-bench-3 --track frames
```

<details><summary>别的 agent CLI，或自己显卡上的视觉模型</summary>

- 任何接在 OpenAI 兼容接口后面的视觉模型（Ollama、LM Studio、vLLM、OpenRouter），用自己的显卡免费跑：同一条命令，换成
  `--agent openai --base-url http://localhost:11434/v1 --model qwen3-vl:4b-instruct-q4_K_M`
- Gemini CLI、Qwen Code、Aider、OpenCode、Cursor CLI、Copilot CLI、Goose：这些预设的参数已对照各 CLI 的 `--help` 核对，但还没人用真 CLI 跑过题目。
  [跑一次，把结果发来（issue #7）](https://github.com/mariusDing/sports-video-coach/issues/7)。

</details>

<a href="https://mariusding.github.io/sports-video-coach/benchmark/zh/"><img src="https://mariusding.github.io/sports-video-coach/benchmark/clip.gif" width="360" alt="基准测试短片：程序画的颠球视频，agent 看到的一次快速连续两触的静帧，再对比真实触球数（47）和各个模型的回答"></a>

## 试一下

**1. 先看成品，不用安装：**[demo 的教练网页](https://mariusding.github.io/sports-video-coach/demo/)，以及它的讲解视频
（[中文](https://mariusding.github.io/sports-video-coach/film.zh.mp4)、[English](https://mariusding.github.io/sports-video-coach/film.en.mp4)）。

**2. 对你的 agent 说**（粘贴到 Claude Code、Codex 或任何编程 agent；把运动和语言换成你的）：

```text
给我的运动视频 <你的视频路径> 做教练复盘。安装任何东西之前先问我，我同意后再装。
安装命令行工具：`uv tool install git+https://github.com/mariusDing/sports-video-coach`（需要 ffmpeg）。
运行 `sports-video-coach run <视频> --sport badminton --lang zh`，它交给你的每一步（退出码 3）都做完，
直到退出码 0，再把教练网页给我看。
```

不需要 GPU。比赛里可以指定看谁：`--focus "穿红衣服的球员"`，或者球衣号码。
只要网页和片段（不要音频、不要讲解视频，也不会把任何内容发给语音合成服务）：加 `--artifacts html`。
终端提示（退出码 3 的提示、写作指南）是英文的，是写给 agent 看的；交付物按 `--lang` 输出。

比赛、练习、训练都行：足球、网球、羽毛球、跑步、健身房、篮球……
给多个视频时，按给出的顺序拼成一条时间线；同一组动作的两个机位，目前最好分成两个单元各跑一次。
我们的测试里，一段 40 秒的视频约 3 分钟、5 个 agent 步骤跑完；整场比赛更久，也更耗 agent 额度。

<details><summary>在自己电脑上跑 demo（约一分钟，不需要 agent，也不需要你的视频）</summary>

程序画的练习视频，复盘是预先写好的，从头渲染到尾：

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # PATH 上要有 ffmpeg
sports-video-coach demo --lang zh en
```

</details>

## 你会拿到什么

<img align="right" width="260" alt="手机上的教练网页：比分、讲解音频、复盘报告" src="https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/mobile.png">

- **一个手机教练网页**：改什么、一个练习、下次可以检查的目标、对应的片段，整份报告还能听。
- **一段讲解视频**：出问题的地方画面暂停，圈出位置，字幕说明原因。
- **背后的看片复盘**：带时间的关键时刻、发生了什么、为什么，存成 json，agent 可以接着用。
- 支持中文、英文、日文、韩文、西班牙文、法文、德文、葡萄牙文（`--lang`；篮球插件：中文和英文）。

**目前做不到的**：agent 看的是帧拼图（默认 30 秒以内的视频每 0.5 秒一帧，3 分钟以内每秒一帧，更长的每 2 秒一帧），
非常快的细节可能落在两帧之间，除非它对那一刻再切一张更密的放大拼图；自动的球员和球跟踪、技术统计要用篮球插件。
每次运行会用掉一些你的 agent 订阅额度。

<br clear="right">

## 怎么工作

1. **工具把视频切成帧拼图**，能量的先量出来（篮球插件还会跟踪球员和球）。
2. **你的 agent 写复盘和报告**。需要眼睛或文字时工具就停下（退出码 3），说清楚要写什么：先是看片复盘，再是报告。
   校验器会告诉 agent 答案还缺什么。
3. **剩下的工具来做**：片段、讲解音频、网页、讲解视频。改了报告再跑一次，只重做受影响的部分。

agent 的完整约定见 [AGENTS.md](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)；
流水线怎么衔接见 [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md)。

## 任何运动

| 插件 | 适用 |
|---|---|
| `generic`（内置） | 任何运动；建议取决于帧里看到的内容（野球也行：`--sport basketball`） |
| `basketball` | 有数据网站链接的联赛比赛，或在克隆的仓库里用 GPU 跟踪：球队和球员页面、投篮分布图（[文档](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)） |
| 你自己的 | `sports-video-coach new-plugin <your-sport>` 生成一个能跑的插件做起点（[指南](https://github.com/mariusDing/sports-video-coach/blob/master/docs/plugins.md)） |

<details><summary><b>给你的 agent 安装</b>（Claude Code 插件、Agent Skills、uv、克隆）</summary>

- **Claude Code：**`/plugin marketplace add mariusDing/sports-video-coach`，然后
  `/plugin install sports-video-coach@sports-video-coach`。
- **任何支持 Agent Skills 的客户端**（Codex、Cursor 等）：`npx skills add mariusDing/sports-video-coach`，或复制
  [skills/sports-video-coach/SKILL.md](https://github.com/mariusDing/sports-video-coach/blob/master/skills/sports-video-coach/SKILL.md)。
- **只装命令行：**`uv tool install git+https://github.com/mariusDing/sports-video-coach`（约 60 MB，不含 torch；
  PATH 上要有 ffmpeg），然后 `sports-video-coach plugins` 和 `sports-video-coach run <视频> --sport <运动>`。
- **改代码、写插件：**`git clone` 后 `uv sync --no-group basketball`（Python 3.11，不装 torch），命令前加 `uv run`。`uv run pytest -q` 照常能跑。
- **从克隆做篮球跟踪：**`git clone` 后 `uv sync`（Python 3.11，CUDA torch，几 GB），命令前加 `uv run`。
- 没有 git 或被代理挡住：从 `https://github.com/mariusDing/sports-video-coach/archive/refs/heads/master.zip` 安装。
- 提示 `command not found`：运行 `uv tool update-shell` 再开新终端；Git Bash 里 PATH 中的 `C:/...` 要写成 `/c/...`（例如 `/c/Users/<you>/.local/bin`）。

</details>

<details><summary><b>需要什么、花多少钱、哪些数据会离开你的电脑</b></summary>

| | |
|---|---|
| **工具** | 一个编程 agent、[uv](https://docs.astral.sh/uv/)（Python 3.11，uv 会自己下载）、PATH 上的 ffmpeg 和 ffprobe |
| **费用** | 免费（MIT）+ 你的 agent 订阅 |
| **会离开你的电脑** | agent 读的内容（帧拼图、数据、报告）会发给它的模型服务商；讲解文字会发给在线语音合成服务 |
| **只在你要求时** | 用 `--publish` 在 Cloudflare 上生成不公开列出的链接（拿到链接的人都能打开） |

单个视频留在原处；帧、片段和报告放在工作区文件夹。不会发给任何统计或埋点服务。
网页里有真人：只分享给出现在里面的人。详见 [docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md)。

</details>

<details><summary><b>给开发者：退出码 3 模式</b></summary>

一个可续跑的命令行：需要 agent 的眼睛或文字时就以退出码 3 停下，每个 agent 步骤都有校验器（检查必需的文件和复盘字段），并按文件判断新旧，
所以中断后从停下的地方继续，改动后只重做变旧的部分。
架构见 [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md)；
项目最初是 `hoop-tape-miner`，给一支业余篮球队用的看片室（[docs/basketball.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)）。

</details>

## 状态与贡献

早期（alpha）：作者在自己的比赛、训练和合成测试上开发和测试。
欢迎贡献你熟悉的运动的插件、提示词、修复和文档：
[CONTRIBUTING.md](https://github.com/mariusDing/sports-video-coach/blob/master/CONTRIBUTING.md)、
[good first issues](https://github.com/mariusDing/sports-video-coach/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)。
不要在 issue 或 PR 里附上真实球员的视频、帧或名字。
如果它帮到了你，点个 star，能让更多运动员找到它。

[MIT](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)。运行时下载的模型保留各自的许可证。
