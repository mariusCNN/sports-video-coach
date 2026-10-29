<div align="center">

# sports-video-coach

### 让你的 coding agent 当你的运动教练。

[English](https://github.com/mariusDing/sports-video-coach/blob/master/README.md) · **中文**

写给自己练的成年人：用手机拍一次训练，你的 agent（Claude Code、Codex……）告诉你哪里要改、怎么练。

<a href="https://mariusding.github.io/sports-video-coach/#training-example"><img alt="43 秒真实训练复盘：作者自己的投篮训练、定格圈注、两次动作对照、下次练习建议" src="https://github.com/mariusDing/sports-video-coach/releases/download/showcase-2026-10-29/poster-en-wide.jpg" width="720"></a>

**[▶ 看一段真实训练复盘（43 秒，英文）](https://mariusding.github.io/sports-video-coach/#training-example)** · [竖版](https://github.com/mariusDing/sports-video-coach/releases/download/showcase-2026-10-29/sports-video-coach-en-vertical.mp4)<br>
<sub>作者自己的训练，agent 复盘，为展示节选。不代表训练前后改善，也不是命中率测量。</sub>

</div>

## 我为什么做这个

我在一个成年人业余联赛打篮球。很长一段时间我一直按老样子练，就是没进步。

请私教很贵，训练班大多是给小孩开的。少数成人班，要么贵，要么离家远。

联赛本来就会录比赛，训练我自己用手机拍，工作上也一直在用 coding agent。
于是我教 agent 像教练那样看我的录像：哪里出了问题、为什么，用哪个练习去改，下次检查什么。

我自己的比赛和训练都用它复盘过。它免费、开源，别的运动也能用。

## 一句话开始

把这段话粘贴到 Claude Code、Codex 或其他编程 agent：

```text
帮我分析我的运动视频：<视频路径>
克隆 https://github.com/mariusDing/sports-video-coach ，按里面的 START.md 一步步做。
```

**接下来会发生什么**：你的 agent 克隆仓库，照着 [START.md](START.md) 做。装任何东西之前先把命令给你看，你同意才装；
要问的一次问完；然后看你的视频，直到教练网页和讲解视频做好，最后问你要不要排下次训练的计划。
<sub>跑在你自己的电脑上，视频不用上传到任何 App。AI 分析走你自己的 agent 账号。</sub>

<div align="center">

[完整功能](docs/features.md) · [篮球插件](docs/basketball.zh.md) · [Agent 入口](llms.txt)

**试一下：**[demo 网页，不用安装](https://mariusding.github.io/sports-video-coach/demo/) ·
[在 Codespaces 里打开](https://codespaces.new/mariusDing/sports-video-coach)

[![release](https://img.shields.io/github/v/release/mariusDing/sports-video-coach)](https://github.com/mariusDing/sports-video-coach/releases)
[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)
[![Works with Claude Code and Codex](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex%20%7C%20AGENTS.md-8A2BE2.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)

<img alt="作者自己投篮练习的真实运行：原片、agent 的看片复盘在出手后收手定住的地方暂停，然后是教练网页" src="https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/real-session.gif" width="720">

<sub>作者自己投篮练习的一次真实运行：你的视频 → agent 看片复盘 → 你的教练网页。
不用安装就能看完整示例：<a href="https://mariusding.github.io/sports-video-coach/demo/">demo 网页</a>（程序画的练习）。</sub>

</div>

用手机拍下自己：一场比赛、一组练习、一次训练，什么运动都行（跑步、健身、HYROX、足球……篮球的插件做得最深）。
你的编程 agent（Claude Code、Codex、Cursor 等）看带时间戳的帧拼图来复盘，需要时可以再要一张更密的拼图，看清快动作的那一刻。
你拿回一个手机网页：关键片段、每个问题的练习方法和目标、报告的语音版，还有一段讲解视频。
工具在你自己的电脑上跑；agent 看的帧会发给它的模型服务商，和你给它看的其他东西一样。免费，MIT 协议。

## 试一下

**1. 先看成品，不用安装：**[demo 的教练网页](https://mariusding.github.io/sports-video-coach/demo/)，以及它的讲解视频
（[中文](https://mariusding.github.io/sports-video-coach/film.zh.mp4)、[English](https://mariusding.github.io/sports-video-coach/film.en.mp4)）。

**2. 或者把每一步写清楚交给 agent**（[一句话开始](#一句话开始)会替你做完这些；把运动和语言换成你的）：

```text
给我的运动视频 <你的视频路径> 做教练复盘。安装前先把完整的安装命令给我看，我同意后再装。
安装命令行工具：`uv tool install git+https://github.com/mariusDing/sports-video-coach@6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a`（需要 ffmpeg）。
运行 `sports-video-coach run <视频> --sport badminton --lang zh`，它交给你的每一步（退出码 3）都做完，
直到退出码 0，再把教练网页给我看。
```

不需要 GPU。比赛里可以指定看谁：`--focus "穿红衣服的球员"`，或者球衣号码。
只要网页和片段（不要音频、不要讲解视频，也不会把任何内容发给语音合成服务）：加 `--artifacts html`。
终端提示（退出码 3 的提示、写作指南）是英文的，是写给 agent 看的；交付物按 `--lang` 输出。

跑一次步、练一次健身或 HYROX、踢一场球、做一组练习都行：跑步、健身、HYROX、足球、网球、篮球……
给多个视频时，按给出的顺序拼成一条时间线；同一组动作的两个机位，目前最好分成两个单元各跑一次。
我们的测试里，一段 40 秒的视频约 3 分钟、5 个 agent 步骤跑完；整场比赛更久，也更耗 agent 额度。

<details><summary>在自己电脑上跑 demo（约一分钟，不需要 agent，也不需要你的视频）</summary>

程序画的练习视频，复盘是预先写好的，从头渲染到尾：

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach@6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a   # PATH 上要有 ffmpeg
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

### 为什么用这个项目

| 能力 | 带来的价值 |
|---|---|
| **完整教练流程** | 一次可恢复运行，串起复盘、改进动作、训练方法、量化目标、证据片段、语音报告和讲解视频。 |
| **Agent 可直接操作** | Claude Code、Codex 等通过退出码、JSON、写作指南和 `AGENTS.md` 接力，不依赖专有 agent 编排服务。 |
| **任何运动 + 篮球深度分析** | 通用流程不需要 GPU；篮球插件增加球队/球员报告、联赛数据、四要素、回合、阵容、投篮图和对手分析。 |
| **证据可核验** | 原视频时间戳、人工复核状态、标定质量门槛、源文件/权重哈希、独立标签评估；自动候选与已确认事实分开。 |
| **覆盖比赛与训练** | 投篮训练、动作复盘、训练计划、场上提示音频、赛季汇总、对手档案、战术回放和手机竖屏片段。 |
| **可扩展、可复现** | 运动插件、本地模型适配、阶段缓存，以及有精确真值的合成录像理解基准。 |

[完整功能与命令目录](docs/features.md) 列出了各项能力的条件和限制。

### 可选篮球视觉增强

- **OpenHoopVision**：投篮、传球、运球、篮板和球权变化候选；姿态、球衣号码/OCR、身份线索；复核冲突、证据片段和双语验证卡片。
- **SAHI**：同一篮球 RF-DETR 权重上的重叠切片检测、坐标还原和去重；与全图检测一起测召回、误检和耗时。
- **WASB**：三帧篮球热图定位，输出原视频坐标；没有可靠观测时明确留空。
- **KaliCalib**：学习球场关键点，生成 FIBA 球场映射候选，经过几何门槛和独立交点验证；失败时不回退到默认球场。

这些适配器已接入并在私有业余比赛录像上实测，**仍为可选实验功能，不保证提升准确率**。
一次 45 帧诊断中，SAHI 将最高分球候选命中从 20/35 提高至 22/35，同时误检帧从 11 增至 13，推理约慢 4.2 倍。
WASB 漏掉了大部分可见球，KaliCalib 尚不适合自动替换标定。[方法、实测结果、安装与许可](docs/perception-lab.md)。

本 README 的安装示例已固定到包含新适配器的已测实现。篮球视觉需要跟踪环境；
[接入指南](docs/perception-lab.md) 给出上游固定版本和可选依赖。
运行 `hoop-tape-miner perception-lab --help` 可以检查入口。

### 运行循环

1. **工具把视频切成帧拼图**，能量的先量出来（篮球插件还会跟踪球员和球）。
2. **你的 agent 写复盘和报告**。需要眼睛或文字时工具就停下（退出码 3），说清楚要写什么：先是看片复盘，再是报告。
   校验器会告诉 agent 答案还缺什么。
3. **剩下的工具来做**：片段、讲解音频、网页、讲解视频。改了报告再跑一次，只重做受影响的部分。

agent 的完整约定见 [AGENTS.md](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)；
流水线怎么衔接见 [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md)。

## 任何运动

| 插件 | 适用 |
|---|---|
| `generic`（内置） | 任何运动：跑步、健身、HYROX、足球、网球……；由 agent 看录像复盘，暂时没有专项跟踪和知识库（野球也行：`--sport basketball`） |
| `basketball` | 有数据网站链接的联赛比赛，或在克隆的仓库里用 GPU 跟踪：球队和球员页面、投篮分布图（[文档](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)） |
| 你自己的 | `sports-video-coach new-plugin <your-sport>` 生成一个能跑的插件做起点（[指南](https://github.com/mariusDing/sports-video-coach/blob/master/docs/plugins.md)） |

<details><summary><b>给你的 agent 安装</b>（Claude Code 插件、Agent Skills、uv、克隆）</summary>

- **Claude Code：**`/plugin marketplace add mariusDing/sports-video-coach`，然后
  `/plugin install sports-video-coach@sports-video-coach`。
- **任何支持 Agent Skills 的客户端**（Codex、Cursor 等）：`npx skills add mariusDing/sports-video-coach`，或复制
  [skills/sports-video-coach/SKILL.md](https://github.com/mariusDing/sports-video-coach/blob/master/skills/sports-video-coach/SKILL.md)。
- **只装命令行：**
  `uv tool install git+https://github.com/mariusDing/sports-video-coach@6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a`
  （约 60 MB，不含 torch；PATH 上要有 ffmpeg），然后 `sports-video-coach plugins` 和
  `sports-video-coach run <视频> --sport <运动>`。
- **改代码、写插件：**`git clone https://github.com/mariusDing/sports-video-coach`，进目录后
  `git checkout 6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a`（或你选的分支），
  再 `uv sync --no-group basketball`（Python 3.11，不装 torch），命令前加 `uv run`。`uv run pytest -q` 照常能跑。
- **从克隆做篮球跟踪**：同样克隆并 checkout 后 `uv sync`（Python 3.11，CUDA torch，几 GB），命令前加 `uv run`。
- 每条安装命令都固定到同一个提交，装的就是你读过的代码；换版本时更新日志会写明。
- 没有 git 或被代理挡住：从 `https://github.com/mariusDing/sports-video-coach/archive/6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a.zip` 安装。
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

## 基准测试：哪个 agent 看运动录像最准

程序画的练习视频，按工具自己画进去的精确真值打分。不用评审模型。

- **新种子榜**（只看静帧，每次运行用一个没公开过的新种子，分数是比盲猜高出的部分取平均，1 = 全对）：
  Codex gpt-6-astra 1.000 · Claude Opus 5.5 0.997（low effort 时 0.778）· Claude Sonnet 5.5 默认 effort 0.419，high 时 0.931（4 次，0.856–0.994；max 超时）·
  本地显卡上的 qwen3-vl 4B 0.000。
  每个设置跑了一到四次；目前所有运行都是作者自己跑的。
- [中文排行榜](https://mariusding.github.io/sports-video-coach/benchmark/zh/#frames-svc-bench-3-fresh) · [自己数一数触球](https://mariusding.github.io/sports-video-coach/benchmark/zh/#count) · [方法和提交方式](https://github.com/mariusDing/sports-video-coach/blob/master/docs/benchmark.md)（英文）
- 重跑新种子榜：先安装（需要 ffmpeg），再跑一条命令（`--seed` 抽一个新种子；
  加上 `--model claude-sonnet-5-5 --effort high` 就是重跑 Sonnet 5.5 high 那一项）：

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach@6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a
sports-video-coach bench run --agent claude --suite svc-bench-3 --track frames --seed
```

- 不想在本机安装：[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/mariusDing/sports-video-coach)
  （用你自己 GitHub 账号的免费时长；在里面登录你的 agent，再在命令前面加上 `uv run`；
  [说明](https://github.com/mariusDing/sports-video-coach/blob/master/docs/benchmark.md#rerun-it-in-the-browser)，英文）。

<details><summary>别的 agent CLI，或自己显卡上的视觉模型</summary>

- 任何接在 OpenAI 兼容接口后面的视觉模型（Ollama、LM Studio、vLLM、OpenRouter），用自己的显卡免费跑：同一条命令，换成
  `--agent openai --base-url http://localhost:11434/v1 --model qwen3-vl:4b-instruct-q4_K_M`
- Gemini CLI、Qwen Code、Aider、Cursor CLI、Copilot CLI、Goose：这些预设的参数已对照各 CLI 的 `--help` 核对，但还没人用真 CLI 跑过题目。
  OpenCode 用免费模型、不登录跑过：计入一次，0.000，到时限被杀时还没写答案（快结束时免费额度用完）；另有三次不计入（我们预设的 bug，以及两次免费额度用完）（[详情](docs/benchmark.md#opencode-run-once-2026-10-25)）。
  [跑一次，把结果发来（issue #7）](https://github.com/mariusDing/sports-video-coach/issues/7)。

</details>

<a href="https://mariusding.github.io/sports-video-coach/benchmark/zh/"><img src="https://mariusding.github.io/sports-video-coach/benchmark/clip.gif" width="360" alt="基准测试短片：程序画的颠球视频，agent 看到的一次快速连续两触的静帧，再对比真实触球数（47）和各个模型的回答"></a>

## 状态与贡献

早期（alpha）：作者在自己的比赛、训练和合成测试上开发和测试。

- [x] 通用运动复盘、多语言报告、片段、语音和讲解视频。
- [x] 篮球比赛、个人训练、球队/球员流程和赛季工具。
- [x] OpenHoopVision 证据接入，以及可选 WASB / SAHI / KaliCalib 对照适配器。
- [ ] 扩大不同球馆、机位的独立验证，再决定是否将实验模型作为默认流程。

欢迎贡献你熟悉的运动的插件、提示词、修复和文档：
[CONTRIBUTING.md](https://github.com/mariusDing/sports-video-coach/blob/master/CONTRIBUTING.md)、
[good first issues](https://github.com/mariusDing/sports-video-coach/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)。
不要在 issue 或 PR 里附上真实球员的视频、帧或名字。

## 教练知识库：欢迎一起完善

篮球报告里的建议来自四个知识库，共 58 条（团队打法、个人技术、跑动与发力、饮食与恢复）。
内容参考公开的 FIBA / Jr. NBA 教练资料和运动科学研究，用我们自己的话写成，每条都注明出处。
用一句话开始分析篮球视频时，agent 会按这些条目给出改进点和练习，并写明用的是哪一条；没有合适的条目，就说明这是它自己的建议。
条目只用来指导建议；快速开始不做跟踪，也不做测量。
[知识库里有什么、怎么补充](https://github.com/mariusDing/sports-video-coach/blob/master/docs/knowledge-base.md)。

- **什么运动都行：先用起来，再一起补充**。跑步、健身、HYROX、足球，都可以用[一句话开始](#一句话开始)跑一遍。
  通用插件什么运动都能看录像复盘，但这些运动还没有自己的跟踪和知识库。告诉我们你这项运动的教练会看什么。提一个[教练知识 issue](https://github.com/mariusDing/sports-video-coach/issues/new?template=coaching_knowledge.yml)就够了，不用写代码。
- 篮球条目的纠错、更新的研究、更好的练习方法，也欢迎这样提。

<sub>与 FIBA、NBA 及所引用的作者均无关联，也未获其认可。</sub>

## 支持

[![GitHub stars](https://img.shields.io/github/stars/mariusDing/sports-video-coach?logo=github&label=star)](https://github.com/mariusDing/sports-video-coach)

免费开源，是一个打业余联赛的球员用空闲时间做的。
觉得有用，就去 GitHub 点个 ☆ star。看到 star，我就知道它真帮到了人，也能让更多打球的人找到它。
分析顺利跑完后，你的 agent 只会问你一次，你点头它才会帮你点。

[MIT](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)。运行时下载的模型保留各自的许可证。
