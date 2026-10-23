# sports-video-coach

**你的 AI agent 看你的比赛录像，像教练一样给你指导。**

[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/pyproject.toml)
[![Agent: Claude Code | Codex](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex-8A2BE2.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)
[![在线示例](https://img.shields.io/badge/demo-live-2ea44f.svg)](https://mariusding.github.io/sports-video-coach/)

[English](https://github.com/mariusDing/sports-video-coach/blob/master/README.md) · 中文

丢进一段手机拍的比赛或训练视频。
Claude Code 或 Codex 像教练一样看片，交回一个手机网页：片段、讲解音频、练习方法，和下次要达到的目标。
全部在你自己的电脑上跑。

**状态：**早期（alpha）。由作者在自己的比赛和合成测试上开发、测试；欢迎通过 [issues](https://github.com/mariusDing/sports-video-coach/issues) 反馈或贡献插件。

## 一分钟试用

**不想安装：**[打开 demo 生成的教练网页](https://mariusding.github.io/sports-video-coach/demo/)（片段、讲解音频），以及讲解视频（[中文](https://mariusding.github.io/sports-video-coach/film.zh.mp4)、[English](https://mariusding.github.io/sports-video-coach/film.en.mp4)）。它们由 CI 用下面的 `demo` 命令重新生成。

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # PATH 上要有 ffmpeg
sports-video-coach demo --lang zh en                      # 约一分钟：网页、片段、讲解音频、讲解视频
```

[![demo 生成的讲解视频：方块停住的地方画面暂停、圈出来，字幕说明原因](https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/demo-film.gif)](https://mariusding.github.io/sports-video-coach/film.zh.mp4)

- 视频是程序画的（红色方块在锥桶间折返跑），复盘是预先写好的：不需要 agent，也不需要你自己的视频，就能看到全部交付物。
- `--offline`：不联网，只出片段和网页。
- 换成你自己的视频时，复盘由你的 agent 来写，见[给 agent：从这里开始](#给-agent从这里开始)。

<details><summary>安装遇到问题？（下载大小、代理、PATH）</summary>

- 安装约下载 60 MB（主要是 OpenCV 和 NumPy，不含 torch）。
- 没装 git，或 git 被代理挡住：`uv tool install https://github.com/mariusDing/sports-video-coach/archive/refs/heads/master.zip`。
- 装完提示 `sports-video-coach: command not found`：运行 `uv tool update-shell`，再开一个新终端。
  或者在 bash（包括 Git Bash）里：`export PATH="$HOME/.local/bin:$PATH"`（默认位置；`uv tool dir --bin` 显示你的位置）。
- Git Bash：uv 的提示是 PowerShell 写法；`C:/...` 的 bin 目录在 PATH 里要写成 `/c/...`
  （`export PATH="/c/Users/<you>/.local/bin:$PATH"`）。

</details>

如果看完 demo 你也想给自己的比赛来一份，点个 star，能让更多运动员找到它。

## 适合谁

- **运动员：**交一次训练，拿回：改什么、一个练习、下次怎么检查。
- **教练：**交一场比赛，拿回：一个球队页面，每个球员一个页面，带片段和音频，用私密链接分享。
- **开发者：**模式是一个可续跑的命令行，需要 agent 的眼睛或文字时就以退出码 3 停下，每个 agent 步骤都有校验器。
  可复用到任何 agent + 媒体的流水线；新运动插件一条命令。

## 你需要什么

| | |
|---|---|
| **工具** | 一个编程 agent（Claude Code、Codex、Cursor 等）、[uv](https://docs.astral.sh/uv/)、PATH 上的 ffmpeg |
| **费用** | 免费（MIT）+ 你的 agent 订阅 |
| **语言** | 中文、英文、日文、韩文、西班牙文、法文、德文、葡萄牙文：`--lang zh en ja ko es fr de pt`（篮球插件：中英） |
| **会离开你电脑的** | agent 读到的内容（截帧拼版、数据、报告）会发给它的模型服务商；朗读文本会发到在线语音合成服务 |
| **只在你要求时** | Cloudflare 上的私密链接，加 `--publish` |

视频不会上传到任何分析服务。细节：[docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md)。

![示例输出（篮球插件）：比分、讲解音频、教练复盘](https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/hero.png)

## 给 agent：从这里开始

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # 轻量安装，不含 torch；PATH 上要有 ffmpeg
sports-video-coach plugins                                # 看哪个插件适合这个视频（--json）
sports-video-coach run my_video.mp4 --sport badminton     # generic 插件；建 workspace/analysis/badminton/<日期>/
                                                          # （--lang zh en 出中英两份；run --help 列出全部选项）
# 退出码 3：按输出做完那一步，再对它建好的文件夹运行一次
sports-video-coach run workspace/analysis/badminton/2025-03-15
```

要 fork、写插件或用篮球跟踪：`git clone` 本 repo 再 `uv sync`（Python 3.11，会连同 CUDA 版 torch 装上篮球的视觉依赖），命令前加 `uv run`。

约定（退出码、选插件、交付物、点星礼仪）见 [AGENTS.md](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)。

- Claude Code：先 `/plugin marketplace add mariusDing/sports-video-coach`，再 `/plugin install sports-video-coach@sports-video-coach` 装上 skill；在克隆的 repo 里用 `/analyze <视频>`。
- 其他支持 Agent Skills 的客户端（Codex、Cursor 等）：`npx skills add mariusDing/sports-video-coach`，或直接复制 [skills/sports-video-coach/SKILL.md](https://github.com/mariusDing/sports-video-coach/blob/master/skills/sports-video-coach/SKILL.md)。

## 你会得到

| 交付物 | 是什么 |
|---|---|
| `run/review/review.json` | 录像复盘：带时间的片段、发生了什么、为什么 |
| `README.<lang>.md` | 教练报告：练什么、怎么练、可检查的目标（中文报告是 `README.md`，不是 `README.zh.md`） |
| `clips` | 报告标出的关键片段 |
| `narration` | `listen.<lang>.mp3`，报告的朗读版 |
| `html` + `qa` | `index.html`，手机友好的单页，含片段和音频，分享前已检查 |
| `publish` | 每个页面一个私密链接（Cloudflare Workers，可选） |
| `film` | `film.<lang>.mp4`，讲解视频：旁白配片段、定格和标注 |

在单元 json 或个人 profile 里写 `"artifacts": ["html", "film"]` 选择交付物；默认全部。

## 工作方式

这个 repo 是流程，**你的 AI agent 就是教练**。

- 命令行负责截帧、测量、记录每一步、生成交付物。
- 需要 agent 看片或写作时，它以退出码 3 停下，并说清楚要做什么。
- 每个 agent 步骤都带校验器，agent 知道自己的输出还缺什么。
- 每一步都知道自己产出哪个文件、读了什么，所以中断后能接着跑，只重做被改动影响的步骤。

```
你的视频 ─▶ 插件 `new` ─▶ 单元文件夹 ─▶ run：命令步骤（截帧、姿态、跟踪……）
                                            agent 步骤（退出码 3：看片、写作）◀─ 你的 agent
                                          ─▶ 片段 ▶ 朗读 ▶ 页面 ▶ QA ▶ 发布 ▶ 讲解视频
```

用 demo 的折返跑视频真实跑一次（路径已缩短，长行用 `...` 截断；输出是英文）：

```console
$ sports-video-coach run drill.mp4 --sport tennis
[run] plugin: generic (no plugin named for --sport tennis; `--plugin NAME` picks one)
[run] frames: sports-video-coach frames drill.mp4 --out .../run/frames --every 0.5
frames: 4 sheets (0.5 s per tile) in .../run/frames
[run] waiting for the agent: review
Film review: open every sheet in .../run/frames (frames.json lists them in time order) and write
.../run/review/review.json as the review guide says (`sports-video-coach guide review --unit ...` ...) ...
[run]   .../run/review/review.json missing                                     # 退出码 3

$ sports-video-coach run workspace/analysis/tennis/2025-03-15                  # agent 写了一份太薄的复盘
[run] waiting for the agent: review
[run]   .../run/review/review.json: needs a `moments` list with at least 3 entries   # 退出码 3：校验器

$ sports-video-coach run workspace/analysis/tennis/2025-03-15                  # agent 补好了
[run] waiting for the agent: report
Write the coaching report README.en.md in ... from .../run/review/review.json, as
`sports-video-coach guide report --unit ...` says (en) ...                      # 退出码 3：下一步
```

细节：[docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md)。

## 插件

| 插件 | 适用 | 增加了什么 |
|---|---|---|
| `generic`（内置） | 任何运动或活动、任何片段；野球、手机片段、没有联赛或没有 GPU 的篮球也用它（`--sport basketball`） | 缩略图拼版 ▶ agent 看片 ▶ 报告；不做检测，由 agent 看截帧 |
| `basketball`（[文档](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.zh.md)） | 联赛比赛（数据网站链接），或在克隆的 repo 里做跟踪（`uv sync`，GPU）；个人训练、跑动 | 球员和球跟踪、联赛数据、球队和球员页面、投篮图、讲解视频里的战术板 |

新运动一条命令：`uv run sports-video-coach new-plugin badminton` 生成一个能直接跑的插件文件夹。然后写它的看片提示词、
加测量。指南：[docs/plugins.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/plugins.md)。分享你的插件时加 GitHub topic `sports-video-coach-plugin`。

## 篮球

项目起点是 `hoop-tape-miner`，一个业余球队的篮球录像室，用法不变：`uv run hoop-tape-miner run <联赛比赛链接>`、
`/game`、`/train`、`/move`。见 [docs/basketball.zh.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.zh.md)。

没有联赛、野球或手机片段：`sports-video-coach run clip.mp4 --sport basketball`（generic 插件，任何片段都行）。

## 隐私

视频、截帧、报告和个人资料都留在 `workspace/`（已 gitignore）。页面里是真实的人，只分享给画面里的人。
朗读文本会发送到在线语音合成服务。见 [docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md)。

## 参与贡献

欢迎插件、你熟悉的运动的提示词、修复和文档：[CONTRIBUTING.md](https://github.com/mariusDing/sports-video-coach/blob/master/CONTRIBUTING.md)。不要在 issue 或 PR 里附上真实球员的视频、截帧或名字。

## 许可

[MIT](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)。运行时下载的模型遵循各自的许可。
