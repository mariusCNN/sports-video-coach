"""`sports-video-coach bench page <results_dir> <out_dir>`: the public benchmark leaderboard.

Reads every `*.json` result file in `<results_dir>` (schema 1, written by `bench score`) and writes
`<out_dir>/index.html` and its Simplified Chinese twin `<out_dir>/zh/index.html` (same rows and numbers, a
language switch and hreflang links both ways): a self-contained static page (inline CSS, light and dark,
readable at 390 px) with the leaderboard ranked by total (above it, a summary per contender: runs, mean total, mean and range of above
chance), with an "above chance" score next to it (the floor is the blind baseline's result
file of that suite and track, `bench.baseline`, shown as a marked row under the ranked ones; under it a folded
"Where each contender fails" block: per task the suite's truth, each run's stored answer, the recomputed score and
what was missed) (one table per suite, the hard suite first; runs on the frames-only track, which
see still images and run no code, in their own tables below), the method, how to run it yourself, how to submit a
run and honesty notes, and `card.png`, the share card link previews show (`bench.card`, needs matplotlib; the
page's `og:image` points at it). With no
results it shows a "no runs yet" state; a file that does not parse is skipped and named in a visible note. The page
never invents a row: every number on it comes from a result file.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from . import card as share_card
from . import clip as share_clip
from . import count as count_it
from . import effort as effort_chart
from . import run as bench_run
from .score import BASELINE_AGENT, SUITES as TRUTH_SUITES, above_chance, is_num, score_task, suite_tasks

OWNER = "mariusDing"           # the repo owner, who also wrote the tool and submitted its first runs
REPO_URL = f"https://github.com/{OWNER}/sports-video-coach"
DOC_URL = f"{REPO_URL}/blob/master/docs/benchmark.md"
RESULTS_URL = f"{REPO_URL}/tree/master/benchmark/results"
ISSUE_URL = f"{REPO_URL}/issues/new?template=benchmark_result.yml"
WANTED_URL = f"{REPO_URL}/issues/7"   # open issue: run an untested preset against the real CLI, send the row
PAGE_URL = "https://mariusding.github.io/sports-video-coach/benchmark/"   # where the demo-site CI publishes it
DEMO_URL = "https://mariusding.github.io/sports-video-coach/demo/"        # the coaching page the demo builds
SUITE = "svc-bench-1"          # a result file without a suite field is from suite 1
SUITES = (                     # (name, what it is), shown in this order; unknown suites follow by name
    ("svc-bench-3", "Eyes: four drawn videos whose events are small, short or hidden: a ball 5 px in radius on a "
                    "640x360 frame, a ball 3 px in radius at a 16 px wide far rim, double touches 0.24 s apart, a "
                    "banner and a defender in front of the moment, pass fakes, and decoys with nearly the same answer (a second juggler, a second pair passing, a far boat "
                    "at a close rate)."),
    ("svc-bench-2", "Hard: five drawn videos with a hand-held camera, look-alike decoys (a second ball, two "
                    "identical feet, a rebounder), rule-defined events and noise."),
    ("svc-bench-1", "Four short drawn videos on a still camera."),
)
FRESH = "-fresh"               # a run drawn from a fresh seed is listed under its suite's name plus this
FRESH_WHAT = ("Fresh seeds: svc-bench-3 drawn anew for each run from the seed in its result file (`--seed`), with "
              "the same scenes and kinds of traps but new counts, outcomes, times and rates. The agent's folder "
              "never held the truth; the tool rebuilds it from the seed to score and check each row, and shows it "
              "below, so a published seed is spent. Each run's floor is the blind baseline on its own seed.")
TRACK = "code"                 # a result file without a track field is on the code track
FRAMES = ("Frames-only track: the agent sees still images of each video (contact sheets with the time under every "
          "still) and has no tool that runs code, so it must review by eye. Same videos, same truth, same scoring "
          "as the code track. The scores measure what the model saw and how much it looked: a model that opens few "
          "stills guesses, and a guess can score well.")
ABOVE = ("Above chance: per task, (score - floor) / (1 - floor), clipped to 0..1, where the floor is the score of "
         "the blind baseline (it copies the example answers from the task text and sees no video); 0 = no better "
         "than that guess, 1 = perfect.")
COSTS = ("Time = wall seconds the run took; cost = USD the agent itself reported (Claude Code does, Codex does "
         "not); '-' = not recorded.")
SUMMARY = ("n = runs of that agent, model and settings; range = lowest to highest above-chance total over them "
           "(a dash for a single run). A run whose settings only add a note (such as being killed at the time "
           "limit) counts with its contender.")
TITLE = "Sports film review benchmark"
WHAT = ("Which coding agent and vision model reviews sports film best, on synthetic drills? Each run is scored "
        "against ground truth the tool drew into the videos, so every number is measured, not judged.")
PART_OF = ("It is part of sports-video-coach, a free MIT tool: your coding agent reviews your own sports video and "
           "writes you a coaching page with clips and drills.")

KINDS = (
    ("count", "How many reps, bounces or shots.", "1 - |error| / truth, never below 0."),
    ("rate", "A cadence or a percentage.", "1 within 2 % of the truth, falling linearly to 0 at 20 %."),
    ("timestamps", "When each event happens.",
     "Per event: 1 within 0.5 s, linear to 0 at 2 s, 0 if missing; summed and divided by the longer of the truth "
     "and answer lists, so extra events cost too."),
    ("outcomes", "Made or missed, in order.", "Fraction of positions answered correctly."),
)
COMMANDS = (
    ("Install (needs ffmpeg on PATH)", f"uv tool install git+{REPO_URL}"),
    ("Make the tasks: videos and an empty answers.json (the newest suite; leave out --suite for svc-bench-1)",
     "sports-video-coach bench prepare --out bench-run --suite svc-bench-3"),
    ("Let your agent watch the videos and fill bench-run/answers.json, then score it",
     'sports-video-coach bench score bench-run --agent "Your agent" --model "your-model"'),
)
NOT_RECORDED = "answer not recorded"
FAILS = ("Every contender run, task by task: the truth (from the suite), each run's answer as its result file stores "
         "it, the score recomputed from the two, and what was missed. The blind baseline is left out. Timestamps: an "
         "event not answered within 0.5 s still earns part of its point up to 2 s off; an unmatched answer is one "
         "with no event within 0.5 s.")
SHOW = 4                       # list diffs name at most this many times or positions, then "+N more"
LANGS = ("en", "zh")          # the page in English (index.html) and Simplified Chinese (zh/index.html)
TAGS = {"en": "en", "zh": "zh-CN"}
URLS = {"en": PAGE_URL, "zh": f"{PAGE_URL}zh/"}
COUNT_VIDEO = "The task video: two players juggle small yellow balls; count the left (red) player's touches."
COUNT_OPEN = "Counted? Open for the truth and every model's answer"
KIND_ZH = {"count": "次数", "rate": "比率", "timestamps": "时间点", "outcomes": "结果"}
# The Chinese page: every English text the page shows, keyed by itself (templates keep their {fields}). `t` raises
# KeyError on a missing entry, so a new English text without a translation fails the zh page's tests.
ZH = {
    SUITES[0][1]: "眼力：四段程序画的视频，事件小、短或被挡住：640x360 画面里半径 5 px 的球，16 px 宽的远处篮筐上半径 "
                  "3 px 的球，相隔 0.24 s 的两次触球，挡在关键时刻前面的横幅和防守人，传球假动作，以及答案几乎一样的"
                  "干扰项（第二个颠球的人、第二对传球的人、节奏相近的远处小船）。",
    SUITES[1][1]: "难：五段程序画的视频，手持镜头，有长得像的干扰项（第二个球、两只一模一样的脚、一个抢篮板的人）、"
                  "按规则定义的事件和噪点。",
    SUITES[2][1]: "四段很短的程序画视频，固定机位。",
    FRESH_WHAT: "新种子：每次运行都按结果文件里的种子（`--seed`）重新画一遍 svc-bench-3，场景和陷阱种类不变，但次数、"
                "结果、时间和节奏都是新的。agent 的文件夹里从来没有答案；工具按种子重建答案来打分、核对每一行，并在下面"
                "展示，所以公开过的种子就作废了。每次运行的基线是它自己那个种子上的盲猜基线。",
    FRAMES: "静帧赛道：agent 只能看每段视频的静帧（拼成的缩略图，每张下面标着时间），没有能运行代码的工具，只能用眼睛"
            "看。视频、真实值和打分方式都和代码赛道相同。分数衡量的是模型看到了什么、看得多仔细：只翻几张静帧的模型是在"
            "猜，而猜也可能拿高分。",
    ABOVE: "超出盲猜：每道题算 (score - floor) / (1 - floor)，限制在 0..1；floor 是盲猜基线的分数（它照抄题目里的示例"
           "答案，不看视频）。0 = 不比这种瞎猜强，1 = 满分。",
    COSTS: "用时 = 这次运行实际花的秒数；费用 = agent 自己报告的美元数（Claude Code 会报，Codex 不报）；'-' = 没有记录。",
    SUMMARY: "n = 同一 agent、模型和设置的运行次数；范围 = 这些运行的超出盲猜总分从最低到最高（只跑一次时为短横）。"
             "设置只多一条备注的运行（比如到时限被终止）算在同一个参赛者里。",
    TITLE: "体育录像复盘基准测试",
    WHAT: "哪个编程 agent 和视觉模型最会看体育录像？用程序画的训练视频来测。每次运行都和工具画进视频里的真实值比对"
          "打分，所以每个数字都是测出来的，不是评出来的。",
    PART_OF: "它属于 sports-video-coach，一个免费的 MIT 工具：你的编程 agent 看你自己的运动视频，给你写一页带片段和"
             "练习的教练复盘。",
    KINDS[0][1]: "多少次颠球、拍球或投篮。",
    KINDS[0][2]: "1 - |误差| / 真实值，最低为 0。",
    KINDS[1][1]: "节奏或百分比。",
    KINDS[1][2]: "与真实值相差 2 % 以内得 1，线性下降，到 20 % 时为 0。",
    KINDS[2][1]: "每个事件发生在什么时候。",
    KINDS[2][2]: "每个事件：0.5 s 以内得 1，到 2 s 线性降为 0，漏掉得 0；求和后除以真实值和回答两个列表中较长的那个，"
                 "所以多报的事件也扣分。",
    KINDS[3][1]: "进还是没进，按顺序。",
    KINDS[3][2]: "按位置答对的比例。",
    COMMANDS[0][0]: "安装（需要 PATH 上有 ffmpeg）",
    COMMANDS[1][0]: "生成题目：视频和一个空的 answers.json（最新的套件；去掉 --suite 就是 svc-bench-1）",
    COMMANDS[2][0]: "让你的 agent 看视频、填好 bench-run/answers.json，然后打分",
    # table
    "transcript": "记录", "link": "链接", "Floor:": "基线：", "(no video seen)": "（没看视频）", "seed {}": "种子 {}",
    "floor": "基线", "Agent": "Agent", "Model": "模型", "Settings": "设置", "Total": "总分",
    "Above chance": "超出盲猜", "Time": "用时", "Cost": "费用", "Date": "日期", "Submitter": "提交者",
    "Evidence": "证据",
    "Scores 0 to 1 per task; total = mean. Ranked by total, then earlier date. {} {} Raw files: {}.":
        "每道题 0 到 1 分；总分 = 平均值。按总分排序，同分时日期早的在前。{} {} 原始文件：{}。",
    # summary
    "Summary": "汇总", "Runs (n)": "次数 (n)", "Mean total": "平均总分", "Mean above chance": "平均超出盲猜",
    "Range": "范围", "Mean time": "平均用时", "Mean cost": "平均费用", "Every run": "每次运行",
    "Ranked by mean above chance; &ldquo;=&rdquo; marks a tie. {} {}":
        "按平均超出盲猜排序；&ldquo;=&rdquo; 表示并列。{} {}",
    "({} of {})": "（{1} 次中有 {0} 次）",
    # where each contender fails
    NOT_RECORDED: "未记录回答", "no answer given": "没有作答", "not a number": "不是数字",
    "{} too many": "多了 {}", "{} too few": "少了 {}", "{}% high": "偏高 {}%", "{}% low": "偏低 {}%",
    "not a list of seconds": "不是秒数列表", "{} of {} not within 0.5 s (at {})": "{1} 个中有 {0} 个不在 0.5 s 内（在 {2}）",
    "{} unmatched (at {})": "{} 个对不上（在 {}）", "all within 0.5 s": "全部在 0.5 s 内", "not a list": "不是列表",
    "#{} said {}": "第 {} 个答成 {}", "{} of {} wrong ({})": "{1} 个中错 {0} 个（{2}）",
    "answered {} of {}": "只答了 {1} 个中的 {0} 个", "{} extra": "多答 {} 个", "; ": "；", ", ": "，",
    " +{} more": " 等，另有 {} 个", "{} time": "{} 次", "{} times": "{} 次", "{} made, {} missed": "进 {}，不进 {}",
    " (M = made)": "（M = 进）", "{} run {}": "{} 第 {} 次", "{} (seed {})": "{}（种子 {}）",
    "score below 1": "未满分", "exact": "完全正确", "truth {}; {}": "真实值 {}；{}",
    "drawn from each run's own seed; shown in its row": "按每次运行自己的种子生成；见各行", "Truth:": "真实值：",
    "Run": "运行", "Answer": "回答", "Score": "得分", "What was missed": "漏在哪里",
    "Where each contender fails": "每个参赛者错在哪里",
    FAILS: "逐题列出每次参赛运行：真实值（来自套件）、结果文件里存的回答、由两者重新算出的分数，以及漏了什么。盲猜基线"
           "不列出。时间点：没在 0.5 s 内答中的事件，偏差在 2 s 以内仍能拿部分分；对不上的回答是指 0.5 s 内没有任何事件"
           "与它对应。",
    # boards, empty, frames
    "No runs on this suite yet.": "这个套件还没有运行记录。",
    " Saturated on this track: all {} runs scored 1.0, so it ranks nobody.":
        "在这个赛道上已经饱和：全部 {} 次运行都是 1.0，排不出高低。",
    "No runs yet — be the first.": "还没有运行记录，来做第一个。",
    "Run the suite with your agent (below), then open a pull request with your result file.":
        "用你的 agent 跑一遍套件（见下文），然后提交一个带结果文件的 pull request。",
    "No frames-only runs yet.": "还没有静帧赛道的运行记录。",
    "Frames-only track (eyes)": "静帧赛道（眼力）",
    "Rerun it in one command: it prepares the suite, runs Claude Code headless with no code tools (or any "
    "CLI with {}), and scores the answers.": "一条命令重跑：准备套件，以无界面模式运行不带代码工具的 Claude Code（或用 {} 运行任意 "
                               "CLI），再给答案打分。",
    "Another agent: prepare the stills, let it fill {} by eye, then score it with {}.":
        "其他 agent：先准备好静帧，让它用眼睛填好 {}，再用 {} 打分。",
    # first screen
    "Latest run {}": "最近一次运行 {}", "Frames-only board ({})": "静帧榜（{}）", "Code-track board": "代码赛道榜",
    "Rerun it in one command": "一条命令重跑", "Code on GitHub": "GitHub 上的代码", "On this page": "本页导航",
    "Before you trust this: {} things a skeptic asks first": "信之前先看：怀疑的人最先会问的 {} 件事",
    # count it yourself
    count_it.QUESTION: "两名球员各用一只脚颠一模一样的黄色小球，侧面视角：左边是红色球员，右边是橙红色球员。数左边（红色）"
                       "球员的触球次数：他的脚每碰到自己的球一次算一次。快速连续两触（球从脚上稍微弹起，马上又被碰到）算两"
                       "次。球落地反弹不算触球。右边球员的触球不算。镜头是手持的。",
    "Count it yourself": "自己数一数",
    "The {} task of {}: the same {} s video every contender got, with no answer drawn on it. Watch it, count, type "
    "your number; only then does the page show the truth and what each model answered.":
        "{1} 里的 {0} 题：和每个参赛者拿到的是同一段 {2} 秒视频，上面没有画答案。看完、数好、填上你的数字，页面才会显示"
        "真实值和每个模型的回答。",
    "The task text the contenders got:": "参赛者拿到的题目（译自英文原文）：",
    COUNT_VIDEO: "题目视频：两名球员颠黄色小球；数左边（红色）球员的触球次数。",
    "Your count": "你数的次数", "Show the answers": "看答案",
    COUNT_OPEN: "数完了？点开看真实值和每个模型的回答",
    "Truth: {} touches": "真实值：{} 次",
    "You counted {n}: off by {d}, which the bench scores {s}.": "你数的是 {n}：差 {d}，按基准的规则得 {s} 分。",
    "frames track": "静帧赛道", "code track": "代码赛道", "Blind guess (no video seen)": "盲猜（没看视频）",
    "How the bench scores a count: {}": "基准怎么给次数题打分：{}",
    "Frames track: the model saw stills of this video, one every {} s, and ran no code. Code track: it could write "
    "and run its own tracker. The blind guess copies the example in the task text.":
        "静帧赛道：模型只看这段视频的静帧（每 {} 秒一张），不能运行代码。代码赛道：它可以自己写追踪程序并运行。盲猜照抄"
        "题目里的示例答案。",
    "Answers as stored in {}, one per run; exact ones in green; &ndash; = the run gave no answer.":
        "回答照搬 {} 里存的，每次运行一个；答对的是绿色；&ndash; = 这次运行没有作答。",
    "Your line to share": "可以分享的一句话", "Copy": "复制", "Copied": "已复制",
    "I counted {n} touches. Truth: {truth}. Models by eye (stills): {models}. Count it yourself: {url}":
        "我数了 {n} 次。真实值：{truth}。模型（只看静帧）：{models}。你也来数：{url}",
    "I counted {n} touches. Truth: {truth}. Models: {models}. Count it yourself: {url}":
        "我数了 {n} 次。真实值：{truth}。模型：{models}。你也来数：{url}",
    # what effort changed (bench.effort: the section and its chart)
    "What effort changed": "effort 改变了什么", ": ": "：",
    effort_chart.TITLE: "同一模型、不同 effort：没见过的种子上的得分",
    effort_chart.SUB: "{} 新种子 · 静帧赛道（只看静帧，不跑代码）· {}",
    effort_chart.FLOOR: "平均超出盲猜：0 = 同一种子上的盲猜（没看视频），1 = 满分。n = 每根柱子的运行次数。",
    effort_chart.LEAD: "同一个模型，同一类题（每次运行都用新种子重新生成 svc-bench-3，只看静帧用眼睛判断）；只改了 effort "
                       "设置。平均超出盲猜：",
    effort_chart.BOUND: "除非标了 n，每个设置只跑了一次，各用自己的种子：这是测出来的差别，不是方差估计。默认 = 没加 effort "
                        "参数（用 CLI 自己的默认值）。每次运行都在下面的榜上有一行。",
    effort_chart.ALT: "柱状图：各 effort 设置的平均超出盲猜分。{}",
    "No contender ran at two effort settings yet.": "还没有参赛者在两种 effort 设置下都跑过。",
    "default effort": "默认 effort", "effort {}": "effort {}",
    "1 run": "1 次运行", "{} runs": "{} 次运行", "; {} gave no answer": "；{} 次没有回答", "{} no answer": "{} 次没回答",
    "{}: no answer, killed at the time limit ({}), scored 0 ({})": "{}：没有回答，到时限（{}）被终止，记 0 分（{}）",
    "{}: no answer, scored 0 ({})": "{}：没有回答，记 0 分（{}）",
    "{}: {} ({}, {} s)": "{}：{}（{}，{} s）",
    "{}: {} mean, range {}–{} ({}, {} s per run{})": "{}：平均 {}，范围 {}–{}（{}，每次 {} s{}）",
    "no answer, timed out at {}": "没有回答，{} 超时", " and ": " 和 ", "no answer": "没有回答", "{} s/run": "每次 {} s",
}


def t(en: str, lang: str) -> str:
    """`en` on the English page, its ZH entry on the Chinese one."""
    return en if lang == "en" else ZH[en]

CSS = """
:root { --bg: #f6f5fb; --card: #fff; --ink: #1d1b38; --muted: #5c5a86; --line: #e2e0ef; --accent: #3b36a8;
        --code-bg: #221f45; --code-ink: #fff; --good: #1d7a46; --warn-bg: #fff4d6; --warn-ink: #6b4d00;
        color-scheme: light; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg: #14132a; --card: #1e1c3b; --ink: #ecebf7; --muted: #a9a7cc;
    --line: #34315c; --accent: #a9a4ff; --code-bg: #0c0b1c; --code-ink: #ecebf7; --good: #6ad79b;
    --warn-bg: #3b3115; --warn-ink: #f3d98b; color-scheme: dark; }
}
:root[data-theme="dark"] { --bg: #14132a; --card: #1e1c3b; --ink: #ecebf7; --muted: #a9a7cc; --line: #34315c;
  --accent: #a9a4ff; --code-bg: #0c0b1c; --code-ink: #ecebf7; --good: #6ad79b; --warn-bg: #3b3115;
  --warn-ink: #f3d98b; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 17px/1.55 system-ui, sans-serif; color: var(--ink); background: var(--bg); }
main { max-width: 52rem; margin: 0 auto; padding: 1.6rem 16px 3rem; }
a { color: var(--accent); }
.name { font-weight: 700; color: var(--muted); margin: 0; }
.name a { color: inherit; text-decoration: none; }
h1 { font-size: clamp(1.5rem, 5vw, 2.2rem); line-height: 1.2; margin: .2rem 0 .6rem; }
h2 { font-size: 1.2rem; margin: 2.2rem 0 .6rem; }
h3 { font-size: 1rem; margin: 0 0 .2rem; }
h4 { font-size: .9rem; margin: .9rem 0 .3rem; }
.lead { margin: 0 0 1rem; max-width: 40rem; }
.chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0; padding: 0; list-style: none; }
nav.jump { margin: .7rem 0 0; font-size: .92rem; }
nav.jump a { display: inline-block; margin: .15rem .9rem .15rem 0; }
.chips li { font-size: .85rem; padding: .15rem .6rem; border-radius: 999px; background: var(--card);
            border: 1px solid var(--line); }
.scroll { overflow-x: auto; background: var(--card); border-radius: 10px; border: 1px solid var(--line); }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { padding: .5rem .6rem; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: .8rem; color: var(--muted); font-weight: 600; }
tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.total { font-weight: 700; color: var(--good); }
td.above { font-weight: 700; }
tr.floor td { background: var(--warn-bg); color: var(--warn-ink); }
td.sub { color: var(--muted); font-size: .85rem; }
.empty { background: var(--card); border: 1px dashed var(--line); border-radius: 10px; padding: 1.2rem 1rem; }
.empty p { margin: .2rem 0; }
.note { background: var(--warn-bg); color: var(--warn-ink); border-radius: 10px; padding: .7rem 1rem;
        margin: .8rem 0; font-size: .9rem; }
.note ul { margin: .3rem 0 0; padding-left: 1.2rem; }
.cards { display: grid; gap: .7rem; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); }
.cards section { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: .8rem 1rem; }
.cards p { margin: .2rem 0; font-size: .92rem; }
.cards .rule { color: var(--muted); }
ol.steps { padding-left: 1.3rem; }
ol.steps li { margin-bottom: .8rem; }
pre { background: var(--code-bg); color: var(--code-ink); border-radius: 10px; padding: .7rem 1rem;
      overflow-x: auto; font-size: .85rem; margin: .3rem 0 0; }
ul.plain { padding-left: 1.2rem; }
ul.plain li { margin-bottom: .3rem; }
footer { margin-top: 2.4rem; color: var(--muted); font-size: .85rem; }
details.fails { margin: 1rem 0 0; background: var(--card); border: 1px solid var(--line); border-radius: 10px;
                padding: .5rem .8rem; }
details.fails summary { cursor: pointer; font-weight: 600; }
details.fails h5 { font-size: .9rem; margin: 1rem 0 .2rem; }
details.fails p.truth { margin: 0 0 .4rem; font-size: .88rem; overflow-wrap: anywhere; }
td.why { white-space: normal; min-width: 11rem; overflow-wrap: anywhere; }
tr.miss td.why { color: var(--warn-ink); background: var(--warn-bg); }
details.facts { margin: 1rem 0 0; background: var(--warn-bg); color: var(--warn-ink); border-radius: 10px;
                padding: .5rem .9rem; font-size: .92rem; }
details.facts summary { cursor: pointer; font-weight: 600; }
details.facts ul { margin: .4rem 0 .2rem; padding-left: 1.1rem; }
details.facts li { margin-bottom: .35rem; }
details.prompt { margin: .8rem 0; }
details.prompt summary { cursor: pointer; font-weight: 600; }
pre.wrap { white-space: pre-wrap; overflow-wrap: anywhere; }
.name a.switch { color: var(--accent); font-weight: 600; margin-left: .6rem; text-decoration: underline; }
.count { margin: 1.4rem 0 0; background: var(--card); border: 1px solid var(--line); border-radius: 10px;
         padding: .2rem 1rem 1rem; }
.count h2 { margin: .8rem 0 .4rem; }
.count blockquote { margin: .4rem 0 .8rem; padding-left: .8rem; border-left: 3px solid var(--line);
                    color: var(--muted); font-size: .9rem; }
.count video { display: block; width: 100%; max-width: 640px; height: auto; border-radius: 8px; background: #000; }
.count [hidden] { display: none; }
.count form { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin: .8rem 0 0; }
.count input { font: inherit; width: 6.5rem; padding: .35rem .5rem; border: 1px solid var(--line); border-radius: 8px;
               background: var(--bg); color: var(--ink); }
.count button { font: inherit; font-weight: 600; padding: .35rem .9rem; border: 0; border-radius: 8px;
                background: var(--accent); color: var(--bg); cursor: pointer; }
.count details { margin: .8rem 0 0; }
.count summary { cursor: pointer; font-weight: 600; }
.count .truth { font-size: 1.15rem; margin: .7rem 0 .3rem; }
.count .you { font-weight: 600; margin: .3rem 0; }
.count ul.answers { list-style: none; margin: .5rem 0; padding: 0; }
.count ul.answers li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .2rem .8rem;
                       padding: .35rem 0; border-bottom: 1px solid var(--line); }
.count ul.answers li:last-child { border-bottom: 0; }
.count .ans { font-variant-numeric: tabular-nums; font-weight: 700; }
.count .ans .exact { color: var(--good); }
.count li.blind { color: var(--muted); }
.count .rule { font-size: .85rem; color: var(--muted); margin: .3rem 0; }
.count textarea { display: block; width: 100%; font: inherit; font-size: .9rem; margin: .3rem 0;
                  padding: .4rem .5rem; border: 1px solid var(--line); border-radius: 8px; background: var(--bg);
                  color: var(--ink); }
.kind { font-size: .75rem; font-weight: 400; color: var(--muted); border: 1px solid var(--line);
        border-radius: 999px; padding: 0 .45rem; margin-left: .3rem; }
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def load(results_dir: Path) -> tuple[list[dict], list[str]]:
    """(rows, notes): the result files that parse as schema 1, and one note per file skipped and why."""
    rows, notes = [], []
    files = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            notes.append(f"{f.name}: not valid JSON ({type(e).__name__})")
            continue
        why = problem(data)
        if why:
            notes.append(f"{f.name}: {why}")
            continue
        data["_file"] = f.name
        rows.append(data)
    rows.sort(key=lambda r: (-float(r["total"]), str(r.get("date", "")), r["_file"]))
    return rows, notes


def problem(data) -> str:
    """Why a parsed file cannot be shown ('' when it can)."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("schema") != 1:
        return f"schema {data.get('schema')!r}, this page reads schema 1"
    if not isinstance(data.get("contender"), dict):
        return "no contender block"
    total = data.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not 0 <= total <= 1:
        return "total is not a number from 0 to 1"
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(t, dict) and "id" in t for t in tasks):
        return "tasks is not a list of tasks with ids"
    return ""


def task_ids(rows: list[dict]) -> list[str]:
    """Every task id, in the order the rows first list them."""
    ids: list[str] = []
    for r in rows:
        for t in r["tasks"]:
            if str(t["id"]) not in ids:
                ids.append(str(t["id"]))
    return ids


def score_cell(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return '<td class="num sub">-</td>'
    return f'<td class="num">{v:.2f}</td>'


def evidence(url, lang: str = "en") -> str:
    url = str(url or "")
    if not url.startswith(("https://", "http://")):
        return '<td class="sub">-</td>'
    label = t("transcript" if "/benchmark/transcripts/" in url else "link", lang)
    return f'<td><a href="{esc(url)}" rel="nofollow noopener">{label}</a></td>'


def is_baseline(r: dict) -> bool:
    """A blind-baseline result file: the floor, not a contender."""
    return r["contender"].get("agent") == BASELINE_AGENT


def seed_floor(suite: str, track: str, seed: int) -> dict | None:
    """{task id: the blind baseline's score} on a fresh seed (computed, never stored), or None for a bad seed."""
    key = (suite, track, seed)
    if key not in _SEED_FLOORS:
        from .baseline import result as blind
        try:
            _SEED_FLOORS[key] = {str(t["id"]): t["score"] for t in blind(suite, track, seed=seed)["tasks"]}
        except (KeyError, ValueError):
            _SEED_FLOORS[key] = None
    return _SEED_FLOORS[key]


_SEED_FLOORS: dict[tuple, dict | None] = {}


def above_value(r: dict, floor: dict | None) -> float | None:
    """A run's above-chance score against `floor`; a run on a fresh seed is measured against its own seed's floor."""
    if r.get("seed") is not None:
        floor = seed_floor(str(r.get("suite") or SUITE), track_of(r), r["seed"])
    return above_chance([{"id": str(t["id"]), "score": t.get("score")} for t in r["tasks"]], floor) if floor else None


def above_cell(r: dict, floor: dict | None) -> str:
    v = above_value(r, floor)
    if v is None:
        return '<td class="num sub">-</td>'
    return f'<td class="num above">{v:.3f}</td>'


def table(rows: list[dict], floor_row: dict | None = None, lang: str = "en") -> str:
    """The ranked rows of one suite and track, then the blind baseline's row (`floor_row`) marked as the floor.
    Without a floor row the above-chance column shows '-'."""
    shown = rows + ([floor_row] if floor_row else [])
    ids = task_ids(shown)
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    head = "".join(f'<th class="num" scope="col">{esc(i)}</th>' for i in ids)
    body = []
    for rank, r in enumerate(shown, 1):
        c = r["contender"]
        base = r is floor_row
        agent = esc(c.get("agent", "")) + (f' <span class="sub">{esc(c["agent_version"])}</span>'
                                           if c.get("agent_version") else "")
        if base:
            agent = f"<strong>{t('Floor:', lang)}</strong> {agent} {t('(no video seen)', lang)}"
        if r.get("seed") is not None:
            agent += f' <span class="sub">{t("seed {}", lang).format(esc(r["seed"]))}</span>'
        scores = {str(t["id"]): t.get("score") for t in r["tasks"]}
        who = esc(r.get("submitted_by") or "-")
        tr = '<tr class="floor">' if base else "<tr>"
        body.append(
            f'{tr}<td class="num">{t("floor", lang) if base else rank}</td><td>{agent}</td>'
            f'<td>{esc(c.get("model") or "-")}</td><td class="sub">{esc(c.get("settings") or "-")}</td>'
            + "".join(score_cell(scores.get(i)) for i in ids)
            + f'<td class="num total">{float(r["total"]):.3f}</td>{above_cell(r, floor)}'
            f'{num_cell(r.get("wall_seconds"), wall)}{num_cell(r.get("cost_usd"), usd)}'
            f'<td>{esc(r.get("date", ""))}</td><td>{who}</td>{evidence(r.get("evidence"), lang)}</tr>')
    col = {k: t(k, lang) for k in ("Agent", "Model", "Settings", "Total", "Above chance", "Time", "Cost", "Date",
                                     "Submitter", "Evidence")}
    note = t("Scores 0 to 1 per task; total = mean. Ranked by total, then earlier date. {} {} Raw files: {}.",
             lang).format(esc(t(ABOVE, lang)), esc(t(COSTS, lang)), f'<a href="{RESULTS_URL}">benchmark/results</a>')
    return (f'<div class="scroll"><table><thead><tr><th class="num" scope="col">#</th>'
            f'<th scope="col">{col["Agent"]}</th>'
            f'<th scope="col">{col["Model"]}</th><th scope="col">{col["Settings"]}</th>{head}'
            f'<th class="num" scope="col">{col["Total"]}</th>'
            f'<th class="num" scope="col">{col["Above chance"]}</th>'
            f'<th class="num" scope="col">{col["Time"]}</th><th class="num" scope="col">{col["Cost"]}</th>'
            f'<th scope="col">{col["Date"]}</th><th scope="col">{col["Submitter"]}</th>'
            f'<th scope="col">{col["Evidence"]}</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">{note}</p>')


def is_num_value(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float))


def wall(v: float) -> str:
    return f"{v:.0f} s"


def usd(v: float) -> str:
    return f"${v:.2f}"


def num_cell(v, fmt) -> str:
    """A time or cost cell: '-' when the run did not record it."""
    return f'<td class="num">{fmt(float(v))}</td>' if is_num_value(v) else '<td class="num sub">-</td>'


def mean_of(runs: list[dict], field: str) -> tuple[float | None, int]:
    """(mean of `field` over the runs that recorded it, how many did)."""
    vals = [float(r[field]) for r in runs if is_num_value(r.get(field))]
    return (sum(vals) / len(vals) if vals else None), len(vals)


def contender_key(r: dict) -> tuple[str, str, str]:
    c = r["contender"]
    return str(c.get("agent") or ""), str(c.get("model") or ""), str(c.get("settings") or "")


def merge_notes(keys: list[tuple[str, str, str]]) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    """Each key mapped to the contender it belongs to: a run whose settings are another run's settings of the same
    agent and model plus a note ("...; killed at the time limit") is the same contender, so its failure counts in
    that contender's mean instead of standing apart."""
    out = {}
    for k in keys:
        bases = [b for b in keys if b[:2] == k[:2] and b[2] and k[2].startswith(b[2] + "; ")]
        out[k] = min(bases, key=lambda b: len(b[2])) if bases else k
    return out


def summarize(rows: list[dict], floor_row: dict | None = None) -> list[dict]:
    """One entry per contender (agent + model + settings) of the given runs: n, mean total, and the mean, min and
    max above chance (None without a floor). Ranked by mean above chance, then mean total, then name. The blind
    baseline is never a contender."""
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    runs_ = [r for r in rows if not is_baseline(r)]
    to = merge_notes(sorted({contender_key(r) for r in runs_}))
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in runs_:
        groups.setdefault(to[contender_key(r)], []).append(r)
    out = []
    for key, runs in groups.items():
        above = [v for v in (above_value(r, floor) for r in runs) if v is not None]
        secs_, n_secs = mean_of(runs, "wall_seconds")
        cost, n_cost = mean_of(runs, "cost_usd")
        out.append({"key": key, "n": len(runs), "total": sum(float(r["total"]) for r in runs) / len(runs),
                    "above": sum(above) / len(above) if above else None,
                    "lo": min(above) if above else None, "hi": max(above) if above else None,
                    "secs": secs_, "n_secs": n_secs, "cost": cost, "n_cost": n_cost})
    out.sort(key=lambda s: (s["above"] is None, -(s["above"] or 0), -s["total"], s["key"]))
    return out


def ranks(summary: list[dict]) -> list[str]:
    """Shown ranks: entries with the same mean above chance and mean total (to 3 decimals) share a rank, marked '='."""
    keys = [(None if s["above"] is None else round(s["above"], 3), round(s["total"], 3)) for s in summary]
    return [f"{keys.index(k) + 1}{'=' if keys.count(k) > 1 else ''}" for k in keys]


def summary_table(rows: list[dict], floor_row: dict | None = None, lang: str = "en") -> str:
    """The per-contender summary of one suite and track, shown above its table of every run."""
    body = []
    summary = summarize(rows, floor_row)
    for rank, s in zip(ranks(summary), summary):
        agent, model, settings = s["key"]
        above = (f'<td class="num above">{s["above"]:.3f}</td>' if s["above"] is not None
                 else '<td class="num sub">-</td>')
        spread = (f'<td class="num">{s["lo"]:.3f}&ndash;{s["hi"]:.3f}</td>' if s["n"] > 1 and s["lo"] is not None
                  else '<td class="num sub">-</td>')
        body.append(f'<tr><td class="num">{rank}</td><td>{esc(agent)}</td><td>{esc(model or "-")}</td>'
                    f'<td class="sub">{esc(settings or "-")}</td><td class="num">{s["n"]}</td>'
                    f'<td class="num total">{s["total"]:.3f}</td>{above}{spread}'
                    f'{part_mean(s["secs"], s["n_secs"], s["n"], wall, lang)}'
                    f'{part_mean(s["cost"], s["n_cost"], s["n"], usd, lang)}</tr>')
    col = {k: t(k, lang) for k in ("Summary", "Agent", "Model", "Settings", "Runs (n)", "Mean total",
                                     "Mean above chance", "Range", "Mean time", "Mean cost", "Every run")}
    note = t("Ranked by mean above chance; &ldquo;=&rdquo; marks a tie. {} {}", lang).format(
        esc(t(SUMMARY, lang)), esc(t(COSTS, lang)))
    return (f'<h4>{col["Summary"]}</h4><div class="scroll"><table class="summary"><thead><tr>'
            f'<th class="num" scope="col">#</th><th scope="col">{col["Agent"]}</th><th scope="col">{col["Model"]}</th>'
            f'<th scope="col">{col["Settings"]}</th><th class="num" scope="col">{col["Runs (n)"]}</th>'
            f'<th class="num" scope="col">{col["Mean total"]}</th>'
            f'<th class="num" scope="col">{col["Mean above chance"]}</th>'
            f'<th class="num" scope="col">{col["Range"]}</th><th class="num" scope="col">{col["Mean time"]}</th>'
            f'<th class="num" scope="col">{col["Mean cost"]}</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">{note}</p><h4>{col["Every run"]}</h4>')


def part_mean(v, n_with: int, n: int, fmt, lang: str = "en") -> str:
    """A mean time or cost cell, with '(k of n)' when only some runs recorded it."""
    if v is None:
        return '<td class="num sub">-</td>'
    part = f' <span class="sub">{t("({} of {})", lang).format(n_with, n)}</span>' if n_with < n else ""
    return f'<td class="num">{fmt(v)}{part}</td>'


def suite_of(r: dict) -> str:
    """The board a run is listed on: its suite, or its suite plus FRESH when it was drawn from a fresh seed."""
    return str(r.get("suite") or SUITE) + ("" if r.get("seed") is None else FRESH)


def track_of(r: dict) -> str:
    return str(r.get("track") or TRACK)


def floor_of(rows: list[dict]) -> dict | None:
    """The floor of one suite and track's rows: its latest blind-baseline result file, or None."""
    base = [r for r in rows if is_baseline(r)]
    return max(base, key=lambda r: (str(r.get("date", "")), r["_file"])) if base else None


def secs(v: float) -> str:
    return f"{float(v):g} s"


def some(items: list[str], lang: str = "en") -> str:
    """At most SHOW items, then '+N more'."""
    head = t(", ", lang).join(items[:SHOW])
    return head + (t(" +{} more", lang).format(len(items) - SHOW) if len(items) > SHOW else "")


def match_events(truth: list[float], answer: list[float], tol: float = 0.5) -> tuple[list[float], list[float]]:
    """(missed truth times, extra answer times): one-to-one pairs within `tol` seconds, closest pairs first."""
    pairs = sorted((abs(t - a), i, j) for i, t in enumerate(truth) for j, a in enumerate(answer) if abs(t - a) <= tol)
    ti, aj = set(), set()
    for _, i, j in pairs:
        if i not in ti and j not in aj:
            ti.add(i)
            aj.add(j)
    return ([t for i, t in enumerate(truth) if i not in ti],
            sorted(a for j, a in enumerate(answer) if j not in aj))


def diff_answer(kind: str, truth, task: dict, lang: str = "en") -> str:
    """What a run got wrong on one task, in a short line ('' when the answer equals the truth). `task` is the result
    file's task row; its `answer` is compared with `truth` (from the suite)."""
    if "answer" not in task:
        return t(NOT_RECORDED, lang)
    ans = task["answer"]
    if ans is None:
        return t("no answer given", lang)
    if kind in ("count", "rate"):
        if not is_num(ans):
            return t("not a number", lang)
        err = ans - truth
        if err == 0:
            return ""
        if kind == "count":
            return t("{} too many" if err > 0 else "{} too few", lang).format(f"{abs(err):g}")
        return t("{}% high" if err > 0 else "{}% low", lang).format(f"{abs(err) / truth * 100:.1f}")
    if kind == "timestamps":
        if not isinstance(ans, list) or not all(is_num(a) for a in ans):
            return t("not a list of seconds", lang)
        missed, extra = match_events([float(x) for x in truth], sorted(float(a) for a in ans))
        bits = []
        if missed:
            bits.append(t("{} of {} not within 0.5 s (at {})", lang).format(
                len(missed), len(truth), some([secs(x) for x in missed], lang)))
        if extra:
            bits.append(t("{} unmatched (at {})", lang).format(len(extra), some([secs(a) for a in extra], lang)))
        return t("; ", lang).join(bits) or t("all within 0.5 s", lang)
    if kind == "outcomes":
        if not isinstance(ans, list):
            return t("not a list", lang)
        norm = [str(x).strip().lower() if x is not None else None for x in ans]
        wrong = [t("#{} said {}", lang).format(i + 1, x) for i, (y, x) in enumerate(zip(truth, norm)) if y != x]
        bits = [t("{} of {} wrong ({})", lang).format(len(wrong), len(truth), some(wrong, lang))] if wrong else []
        if len(norm) < len(truth):
            bits.append(t("answered {} of {}", lang).format(len(norm), len(truth)))
        elif len(norm) > len(truth):
            bits.append(t("{} extra", lang).format(len(norm) - len(truth)))
        return t("; ", lang).join(bits)
    return ""


def show_value(kind: str, v, lang: str = "en") -> str:
    """A truth or answer in a few characters: a number, 'N times', or 'N made, M missed'."""
    if v is None:
        return "-"
    if kind == "timestamps" and isinstance(v, list):
        return t("{} time" if len(v) == 1 else "{} times", lang).format(len(v))
    if kind == "outcomes" and isinstance(v, list):
        made = sum(1 for x in v if str(x).strip().lower() == "made")
        return t("{} made, {} missed", lang).format(made, len(v) - made)
    return f"{v:g}" if is_num(v) else str(v)


def show_truth(kind: str, truth, lang: str = "en") -> str:
    """The truth line of a task: the value, plus the list itself for timestamps and outcomes."""
    if kind == "timestamps":
        return f"{show_value(kind, truth, lang)}: {', '.join(f'{x:g}' for x in truth)} s"
    if kind == "outcomes":
        return (f"{show_value(kind, truth, lang)}: {' '.join('M' if x == 'made' else 'x' for x in truth)}"
                f"{t(' (M = made)', lang)}")
    return show_value(kind, truth, lang)


def run_labels(rows: list[dict], lang: str = "en") -> list[str]:
    """A short name per run: the model (or agent), with 'run k' when several runs share that name."""
    names = [str(r["contender"].get("model") or r["contender"].get("agent") or "?") for r in rows]
    seen: dict[str, int] = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(t("{} run {}", lang).format(name, seen[name]) if names.count(name) > 1 else name)
    return out


def fails(rows: list[dict], suite: str, lang: str = "en") -> list[dict]:
    """Per task of `suite`: {id, kind, truth, runs: [{label, file, answer, score, why, miss}]}, derived from the
    runs' stored answers and the suite's truth (never the truth copied into a result file). The score is recomputed
    (`score_task`); a row without a stored answer keeps its stored score and says the answer was not recorded.
    Empty for a suite this tool does not know. On a fresh-seed board (`suite` ends in FRESH) each run's truth is
    rebuilt from its own seed: the task's truth is then None and every run row carries its own `truth`."""
    base = suite.removesuffix(FRESH)
    mod = TRUTH_SUITES.get(base)
    runs = sorted((r for r in rows if not is_baseline(r)), key=lambda r: r["_file"])
    if mod is None or not runs:
        return []
    labels = run_labels(runs, lang)
    out = []
    for task in mod.TASKS:
        lines = []
        for r, label in zip(runs, labels):
            row = next((x for x in r["tasks"] if str(x["id"]) == task.id), None)
            if row is None:
                continue
            seed = r.get("seed")
            try:
                truth = suite_tasks(base, seed).BY_ID[task.id].truth
            except ValueError:
                continue
            if "answer" in row:
                score = score_task(task.id, row["answer"], base, seed)["score"]
            else:
                score = row.get("score") if is_num(row.get("score")) else None
            why = diff_answer(task.kind, truth, row, lang)
            lines.append({"label": label if seed is None else t("{} (seed {})", lang).format(label, seed),
                          "file": r["_file"], "answer": row.get("answer"), "score": score, "why": why,
                          "miss": score is None or score < 1, "recorded": "answer" in row, "truth": truth})
        if lines:
            same = all(x["truth"] == lines[0]["truth"] for x in lines) and not suite.endswith(FRESH)
            out.append({"id": task.id, "kind": task.kind, "truth": lines[0]["truth"] if same else None,
                        "runs": lines})
    return out


def fails_section(rows: list[dict], suite: str, lang: str = "en") -> str:
    """The folded 'Where each contender fails' block of one suite and track ('' when nothing to show)."""
    tasks = fails(rows, suite, lang)
    if not tasks:
        return ""
    parts = []
    for task in tasks:
        kind = task["kind"]
        body = []
        for x in task["runs"]:
            ans = show_value(kind, x["answer"], lang) if x["recorded"] else "-"
            score = f'{x["score"]:.2f}' if x["score"] is not None else "-"
            why = x["why"] or t("score below 1" if x["miss"] else "exact", lang)
            if task["truth"] is None:
                why = t("truth {}; {}", lang).format(show_truth(kind, x["truth"], lang), why)
            tr = '<tr class="miss">' if x["miss"] else "<tr>"
            body.append(f'{tr}<td title="{esc(x["file"])}">'
                        f'{esc(x["label"])}</td><td class="num">{esc(ans)}</td><td class="num">{score}</td>'
                        f'<td class="why">{esc(why)}</td></tr>')
        truth = (t("drawn from each run's own seed; shown in its row", lang) if task["truth"] is None
                 else show_truth(kind, task["truth"], lang))
        chip = esc(kind) if lang == "en" else f"{KIND_ZH.get(kind, kind)} · {esc(kind)}"
        parts.append(f'<h5>{esc(task["id"])}<span class="kind">{chip}</span></h5>'
                     f'<p class="truth"><strong>{t("Truth:", lang)}</strong> {esc(truth)}</p>'
                     f'<div class="scroll"><table class="fails"><thead><tr><th scope="col">{t("Run", lang)}</th>'
                     f'<th class="num" scope="col">{t("Answer", lang)}</th>'
                     f'<th class="num" scope="col">{t("Score", lang)}</th>'
                     f'<th scope="col">{t("What was missed", lang)}</th></tr></thead>'
                     f'<tbody>{"".join(body)}</tbody></table></div>')
    return (f'<details class="fails"><summary>{t("Where each contender fails", lang)}</summary>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">{esc(t(FAILS, lang))}</p>'
            f'{"".join(parts)}</details>')


def boards(rows: list[dict], prefix: str = "", lang: str = "en", after: dict[str, str] | None = None) -> str:
    """One leaderboard table per suite, in SUITES order (a suite with no runs says so); `prefix` keeps the anchors
    of a second track's tables apart; `after` maps a suite name to HTML shown under its description."""
    known = [n for n, _ in SUITES]
    names = known + sorted({suite_of(r) for r in rows if not is_baseline(r)} - set(known))
    ran = {suite_of(r) for r in rows if not is_baseline(r)}
    names = [n for n in names if n in ran] + [n for n in names if n not in ran]   # empty suites last
    what = dict(SUITES) | {n + FRESH: FRESH_WHAT for n in TRUTH_SUITES}
    out = []
    for n in names:
        mine = [r for r in rows if suite_of(r) == n and not is_baseline(r)]
        floor = floor_of([r for r in rows if suite_of(r) == n])
        none = t("No runs on this suite yet.", lang)
        body = (summary_table(mine, floor, lang) + table(mine, floor, lang) + fails_section(mine, n, lang) if mine
                else f'<p class="sub" style="color:var(--muted)">{none}</p>')
        sat = (t(" Saturated on this track: all {} runs scored 1.0, so it ranks nobody.", lang).format(len(mine))
               if len(mine) > 1 and all(float(r["total"]) == 1 for r in mine) else "")
        desc = f"<p>{esc((t(what[n], lang) if n in what else '') + sat)}</p>" if n in what or sat else ""
        extra = (after or {}).get(n, "")
        out.append(f'<h3 id="{esc(prefix + n)}" style="margin-top:1.4rem">{esc(n)}</h3>{desc}{extra}{body}')
    return "\n".join(out)


def empty(lang: str = "en") -> str:
    return (f'<div class="empty"><p><strong>{t("No runs yet — be the first.", lang)}</strong></p>'
            f"<p>{t('Run the suite with your agent (below), then open a pull request with your result file.', lang)}"
            "</p></div>")


def effort_block(rows: list[dict], drawn=(), lang: str = "en") -> str:
    """"What effort changed" (`bench.effort`), shown on the fresh-seed frames board: the chart (when drawn: the
    page's language, else English), a line per contender from the same data and the bounds of what it measured
    ('' when no contender ran at two effort settings)."""
    data = effort_chart.effort_data(rows)
    if not data["groups"]:
        return ""
    said = effort_chart.lines(data, lang)
    img = ""
    shown = lang if lang in drawn else "en" if "en" in drawn else ""
    if shown:
        up = "" if lang == "en" else "../"
        alt = t(effort_chart.ALT, lang).format(" ".join(said))
        w, h = effort_chart.SIZE
        img = (f'<figure style="margin:.6rem 0"><a href="{up}{effort_chart.NAMES[shown]}"><img '
               f'src="{up}{effort_chart.NAMES[shown]}" alt="{esc(alt)}" width="{w}" height="{h}" loading="lazy" '
               f'style="display:block;width:100%;max-width:{w}px;height:auto;border-radius:10px"></a></figure>')
    items = "".join(f'<li><strong>{esc(g["label"])} · {esc(g["agent"])}</strong><ul>'
                    + "".join(f"<li>{esc(effort_chart.phrase(b, lang))}</li>" for b in g["bars"]) + "</ul></li>"
                    for g in data["groups"])
    return (f'<h4 id="{effort_chart.ANCHOR}">{t("What effort changed", lang)}</h4>{img}'
            f'<p>{esc(t(effort_chart.LEAD, lang))}</p><ul class="plain">{items}</ul>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">{esc(t(effort_chart.BOUND, lang))}</p>')


def frames_board(rows: list[dict], lang: str = "en", effort=()) -> str:
    """The frames-only track's section: its own tables (the fresh-seed board with "What effort changed", the chart
    shown for the languages in `effort`), or a line saying it has no runs yet."""
    mine = [r for r in rows if track_of(r) == "frames"]
    after = {effort_chart.SUITE + FRESH: effort_block(rows, effort, lang)}
    body = boards(mine, "frames-", lang, after) if any(not is_baseline(r) for r in mine) else \
        f'<p class="sub" style="color:var(--muted)">{t("No frames-only runs yet.", lang)}</p>'
    run = "sports-video-coach bench run --agent claude --model <model> --suite svc-bench-3 --track frames"
    prep = "sports-video-coach bench prepare --out bench-frames --suite svc-bench-3 --track frames"
    one = t("Rerun it in one command: it prepares the suite, runs Claude Code headless with no code tools (or any "
            "CLI with {}), and scores the answers.", lang).format('<code>--agent cmd --cmd "... {prompt}"</code>')
    other = t("Another agent: prepare the stills, let it fill {} by eye, then score it with {}.", lang).format(
        "<code>bench-frames/answers.json</code>", "<code>bench score bench-frames</code>")
    return (f'<h2 id="frames">{t("Frames-only track (eyes)", lang)}</h2><p>{esc(t(FRAMES, lang))}</p>'
            f"<p>{one}</p>"
            f'<pre id="rerun"><code>{esc(run)}</code></pre>'
            f"<p>{other}</p>"
            f"<pre><code>{esc(prep)}</code></pre>{body}")


OWN_CONFIG = ("CLAUDE.md loaded", "user config loaded", "AGENTS.md was loaded", "(user config)")


def facts(rows: list[dict], lang: str = "en") -> list[str]:
    """What a skeptic asks first, one short line each, counted from the result files (HTML, already escaped)."""
    runs = [r for r in rows if not is_baseline(r)]
    if not runs:
        return []
    n = len(runs)
    by_owner = sum(1 for r in runs if str(r.get("submitted_by") or "").lower() == OWNER.lower())
    others = n - by_owner
    own = sum(1 for r in runs if any(m in str(r["contender"].get("settings") or "") for m in OWN_CONFIG))
    singles = contenders = 0
    spread = None                                   # (hi - lo, model, suite, track)
    for (suite, track) in sorted({(suite_of(r), track_of(r)) for r in runs}):
        mine = [r for r in rows if suite_of(r) == suite and track_of(r) == track]
        floor = floor_of(mine)
        for x in summarize(mine, floor):
            contenders += 1
            singles += x["n"] == 1
        scores = {str(t["id"]): t.get("score") for t in floor["tasks"]} if floor else None
        same: dict[tuple[str, str, str], list[float]] = {}   # repeats with identical settings: run-to-run noise
        for r in mine:
            v = above_value(r, scores)
            if not is_baseline(r) and v is not None:
                same.setdefault(contender_key(r), []).append(v)
        for key, vals in same.items():
            if len(vals) > 1 and (spread is None or max(vals) - min(vals) > spread[0]):
                spread = (max(vals) - min(vals), key[1] or key[0], suite, track)
    floors = [(t.get("score"), str(t["id"])) for r in rows if is_baseline(r) for t in r["tasks"]
              if is_num(t.get("score"))]
    top = max(floors) if floors else None
    ev = sum(1 for r in runs if str(r.get("evidence") or "").startswith(("https://", "http://")))
    fresh = sum(1 for r in runs if r.get("seed") is not None)
    timed = sum(1 for r in runs if is_num_value(r.get("wall_seconds")))
    costed = sum(1 for r in runs if is_num_value(r.get("cost_usd")))
    if lang == "zh":
        return facts_zh(n, by_owner, others, own, singles, contenders, spread, top, ev, fresh, timed, costed)
    who = (f"all {n} runs were submitted by {esc(OWNER)}, who also wrote this tool; no outside runs yet."
           if not others else f"{by_owner} of {n} runs were submitted by {esc(OWNER)}, who wrote this tool; "
                              f"{others} by others.")
    noise =(f" Two runs with identical settings differed by up to {spread[0]:.3f} above chance "
             f"({esc(spread[1])}, {esc(spread[2])} {esc(spread[3])} track): read smaller gaps as noise. A run "
             "killed at its time limit scores 0 and widens its contender's range further."
             if spread else "")
    guess = (f" That guess alone scores up to {top[0]:.2f} on one task ({esc(top[1])})." if top else "")
    held =(f"{fresh} of {n} runs drew svc-bench-3 from a fresh seed (<code>--seed</code>) at run time, which "
            "reduces the effect of memorising the public answers but proves nothing about training data. The "
            "agent's folder never held that truth; the result file and this page do, so a published seed is spent."
            if fresh else
            "no run used a fresh seed yet. <code>bench prepare --seed</code> draws svc-bench-3 anew at run time, "
            "with no truth in the prepared folder.")
    return [
        f"<strong>Who ran it:</strong> {who}",
        f"<strong>Own config:</strong> {own} of {n} runs say in Settings that the submitter's own agent config "
        "(CLAUDE.md, AGENTS.md or Codex config) was loaded.",
        f"<strong>Sample size:</strong> {singles} of {contenders} contenders (per suite and track) ran once.{noise}",
        "<strong>Settings:</strong> not equalized. Each row ran at the effort and flags its Settings column names.",
        "<strong>Truth:</strong> the tool draws the videos from numbers, so the truth is exact. No human labels, no "
        "judge model.",
        "<strong>Public truth:</strong> the published suites and their truth ship in the open package, so a model "
        f"could have seen them in training; {held}",
        "<strong>Suite design:</strong> svc-bench-2 and svc-bench-3 were each built after models scored 1.0 on the "
        "suite before, so the author knew which models already saturated it.",
        '<strong>Prompt:</strong> <code>bench run</code> sends one fixed text per track, the same for every '
        'model; only the Claude Code frames rows are known to have run with it. See '
        '<a href="#prompt">the exact prompt</a>.',
        "<strong>Above chance:</strong> measured from a blind guess that copies the example answers in the task "
        f"text, not from random.{guess}",
        f"<strong>Evidence:</strong> {ev} of {n} runs link a transcript"
        + (" (in its Evidence column): every file the agent opened, every command it ran and its final reply, with "
           "images, home folders and key-like strings taken out. Anyone can read them; CI re-scores the answers but "
           "does not read the transcripts." if ev else
           ". The no-peeking rule is honour-based: CI re-scores the answers but cannot see what the agent read."),
        f"<strong>Time and cost:</strong> in every table; time recorded for {timed} of {n} runs, cost for "
        f"{costed} of {n}.",
    ]


def facts_zh(n: int, by_owner: int, others: int, own: int, singles: int, contenders: int, spread, top, ev: int,
             fresh: int, timed: int, costed: int) -> list[str]:
    """`facts` on the Chinese page: the same counts, in Chinese."""
    who = (f"全部 {n} 次运行都由这个工具的作者 {esc(OWNER)} 提交；还没有外部提交的运行。"
           if not others else f"{n} 次运行中有 {by_owner} 次由工具作者 {esc(OWNER)} 提交，{others} 次由其他人提交。")
    track = {"code": "代码", "frames": "静帧"}.get(spread[3], esc(spread[3])) if spread else ""
    noise = (f"设置完全相同的两次运行，超出盲猜分最多相差 {spread[0]:.3f}（{esc(spread[1])}，{esc(spread[2])}，"
             f"{track}赛道）：比这小的差距当作噪声看。到时限被终止的运行记 0 分，会让该参赛者的范围更宽。"
             if spread else "")
    guess = f"光靠这种猜法，单道题最高就能拿 {top[0]:.2f}（{esc(top[1])}）。" if top else ""
    held = (f"{n} 次运行中有 {fresh} 次在运行时用新种子（<code>--seed</code>）重新生成 svc-bench-3，这能减少背下公开"
            "答案的影响，但证明不了任何关于训练数据的事。agent 的文件夹里从来没有这份答案；结果文件和本页有，所以公开过的"
            "种子就作废了。"
            if fresh else
            "还没有运行用过新种子。<code>bench prepare --seed</code> 会在运行时重新生成 svc-bench-3，准备好的文件夹里"
            "没有答案。")
    return [
        f"<strong>谁跑的：</strong>{who}",
        f"<strong>自带配置：</strong>{n} 次运行中有 {own} 次在设置栏注明加载了提交者自己的 agent 配置（CLAUDE.md、"
        "AGENTS.md 或 Codex 配置）。",
        f"<strong>样本量：</strong>{contenders} 个参赛者（按套件和赛道分）中有 {singles} 个只跑了一次。{noise}",
        "<strong>设置：</strong>没有统一。每一行按它设置栏写的 effort 和参数运行。",
        "<strong>真实值：</strong>视频是工具按数字画出来的，所以真实值是精确的。没有人工标注，也没有评审模型。",
        f"<strong>真实值是公开的：</strong>公开的套件和真实值都在开源包里，模型可能在训练时见过；{held}",
        "<strong>套件设计：</strong>svc-bench-2 和 svc-bench-3 都是在有模型把前一个套件做到 1.0 之后才做的，所以作者"
        "当时知道哪些模型已经做满分。",
        '<strong>提示词：</strong><code>bench run</code> 每个赛道发一段固定文本，所有模型都一样；只确定 Claude Code '
        '静帧那几行用的是它。见<a href="#prompt">完整提示词</a>。',
        f"<strong>超出盲猜：</strong>起点是照抄题目示例答案的盲猜，不是随机猜。{guess}",
        f"<strong>证据：</strong>{n} 次运行中有 {ev} 次附了对话记录"
        + ("（在证据栏）：agent 打开的每个文件、运行的每条命令和最后的回复，图片、用户目录和像密钥的字符串都已去掉。"
           "任何人都能读；CI 会重新给答案打分，但不读这些记录。" if ev else
           "。不偷看规则靠自觉：CI 会重新给答案打分，但看不到 agent 读了什么。"),
        f"<strong>用时和费用：</strong>每张表都有；{n} 次运行中 {timed} 次记录了用时，{costed} 次记录了费用。",
    ]


def latest(rows: list[dict], lang: str = "en") -> str:
    """A chip with the newest run's date ('' without runs)."""
    dates = [str(r.get("date") or "") for r in rows if not is_baseline(r) and r.get("date")]
    return f"<li>{t('Latest run {}', lang).format(esc(max(dates)))}</li>" if dates else ""


def jump(rows: list[dict], lang: str = "en") -> str:
    """The first-screen links: the frames-only boards (where the headline numbers are), the code-track board, the
    one-command rerun and the repo. A board is linked only when it has runs."""
    shown = {suite_of(r) for r in rows if not is_baseline(r) and track_of(r) == "frames"}
    links = [(f"#frames-{n}", t("Frames-only board ({})", lang).format(n))
             for n in ("svc-bench-3", "svc-bench-3" + FRESH) if n in shown]
    if effort_chart.effort_data(rows)["groups"]:
        links.append((f"#{effort_chart.ANCHOR}", t("What effort changed", lang)))
    if any(not is_baseline(r) and track_of(r) == TRACK for r in rows):
        links.append(("#leaderboard", t("Code-track board", lang)))
    links += [("#rerun", t("Rerun it in one command", lang)), (REPO_URL, t("Code on GitHub", lang))]
    return (f'<nav class="jump" aria-label="{t("On this page", lang)}">'
            + "".join(f'<a href="{esc(h)}">{esc(x)}</a>' for h, x in links) + "</nav>")


def facts_block(rows: list[dict], lang: str = "en") -> str:
    items = facts(rows, lang)
    if not items:
        return ""
    head = t("Before you trust this: {} things a skeptic asks first", lang).format(len(items))
    return (f'<details class="facts" id="facts"><summary>{head}</summary>'
            f'<ul>{"".join(f"<li>{x}</li>" for x in items)}</ul></details>')


def presets_step(lang: str = "en") -> str:
    """The one-command step of "Run it yourself": Claude Code, Codex and one line per preset in bench_run.PRESETS."""
    one = "sports-video-coach bench run --agent {} --suite svc-bench-3"
    checked = "参数已对照 {} 的 --help 核对" if lang == "zh" else "flags checked against {} --help"
    lines = "".join(f"<li><code>--agent {esc(k)}</code> {esc(p.name)}: <code>{esc(bench_run.shown(k))}</code>"
                    f" ({esc(checked.format(p.checked))})</li>" for k, p in bench_run.PRESETS.items())
    pre = f"<pre><code>{esc(one.format('claude'))}\n{esc(one.format('codex'))}</code></pre>"
    if lang == "zh":
        return ("<li>或者一条命令全做完（准备、无界面运行、打分）：Claude Code 或 Codex"
                f"{pre}或者用其他 agent CLI 的预设。这些预设按各 CLI 的文档写成（{esc(bench_run.DOCS_READ)} 读过），"
                f"参数在 {esc(bench_run.HELP_CHECKED)} 对照真实 CLI 的 --help 核对过，"
                "但维护者没有用它们实际跑过题目；只支持代码赛道（"
                f'<a href="{DOC_URL}#add-your-agent-in-one-command">每个参数的文档链接</a>）。其他 CLI：'
                f'<code>--agent cmd --cmd "... {{prompt}}"</code>。<ul class="plain">{lines}</ul>'
                f'用其中某个 agent？跑一次，告诉我们结果：<a href="{WANTED_URL}">issue #7</a>'
                "（发一行结果，或者预设参数不对时的报错）。</li>")
    return ("<li>Or do it all in one command (prepare, run headless, score): Claude Code or Codex"
            f"{pre}"
            "or a preset for another agent CLI. The presets are built from each CLI's docs (read "
            f"{esc(bench_run.DOCS_READ)}), with every flag checked against the real CLI's --help on "
            f"{esc(bench_run.HELP_CHECKED)}, but not run by the maintainer on a task; code "
            f'track only (<a href="{DOC_URL}#add-your-agent-in-one-command">doc links per flag</a>). Any other '
            f'CLI: <code>--agent cmd --cmd "... {{prompt}}"</code>.<ul class="plain">{lines}</ul>'
            f'Use one of these agents? Run it and tell us how it went: <a href="{WANTED_URL}">issue #7</a> '
            "(a result row, or the error if the preset's flags are wrong).</li>")


def prompt_block(lang: str = "en") -> str:
    """The exact prompts `bench run` sends (shown for svc-bench-3; other suites change only the name and count)."""
    code = bench_run.prompt("svc-bench-3", "code")
    frames = bench_run.prompt("svc-bench-3", "frames", "claude")
    if lang == "zh":   # the prompts themselves stay English: they are what the agent was sent
        return ('<details class="prompt" id="prompt"><summary>完整提示词</summary>'
                "<p><code>bench run</code> 发送的原文，一字不改（以 svc-bench-3 为例；其他套件只改套件名和视频数量）。"
                "每个赛道一段文本，所有模型相同。提示词是英文的，这里照原样展示。</p>"
                f'<h4>代码赛道</h4><pre class="wrap" lang="en"><code>{esc(code)}</code></pre>'
                f'<h4>静帧赛道（Claude Code）</h4><pre class="wrap" lang="en"><code>{esc(frames)}</code></pre>'
                "<p>Claude Code 静帧那几行用的就是这段静帧提示词。其他行的结果文件没有存提示词，所以它们用的是什么"
                "不清楚。</p></details>")
    return ('<details class="prompt" id="prompt"><summary>The exact prompt</summary>'
            "<p>What <code>bench run</code> sends, word for word (for svc-bench-3; other suites change only the "
            "suite name and video count). One text per track, the same for every model.</p>"
            f"<h4>Code track</h4><pre class=\"wrap\"><code>{esc(code)}</code></pre>"
            f"<h4>Frames track (Claude Code)</h4><pre class=\"wrap\"><code>{esc(frames)}</code></pre>"
            "<p>The Claude Code frames rows were run with this frames prompt. The other rows do not store their "
            "prompt in the result file, so for them it is unclear.</p></details>")


COUNT_JS = """
(function () {
  var box = document.getElementById("count"), form = document.getElementById("count-form"),
      reveal = document.getElementById("count-reveal"), input = document.getElementById("count-n"),
      you = document.getElementById("count-you"), share = document.getElementById("count-share"),
      line = document.getElementById("count-line"), copy = document.getElementById("count-copy");
  if (!box || !form || !reveal) return;
  var truth = Number(box.getAttribute("data-truth"));
  form.hidden = false;
  reveal.hidden = true;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var n = parseInt(input.value, 10);
    if (!(n >= 0)) { input.focus(); return; }
    var d = Math.abs(n - truth), s = Math.max(0, 1 - d / truth).toFixed(2);
    you.textContent = box.getAttribute("data-you").replace("{n}", n).replace("{d}", d).replace("{s}", s);
    line.value = box.getAttribute("data-line").replace("{n}", n);
    you.hidden = share.hidden = reveal.hidden = false;
    reveal.open = true;
    you.focus();
  });
  copy.addEventListener("click", function () {
    function done() { copy.textContent = box.getAttribute("data-copied"); }
    line.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(line.value).then(done, function () { if (document.execCommand("copy")) done(); });
    } else if (document.execCommand("copy")) { done(); }
  });
})();
"""


def count_answers(runs: list[dict], truth) -> str:
    """A contender's stored answers, one per run: exact ones marked, a run without an answer as a dash."""
    return ", ".join("&ndash;" if r["answer"] is None else
                     f'<span class="exact">{esc(r["answer"])}</span>' if r["answer"] == truth else esc(r["answer"])
                     for r in runs)


def share_line(data: dict, lang: str = "en") -> str:
    """The line a visitor copies, with {n} left for their count: the truth and the frames-track models' answers
    (they looked by eye, as the visitor did; every contender when no frames run exists)."""
    eye = [c for c in data["contenders"] if c["track"] == "frames"]
    models = t("; ", lang).join(
        f'{c["label"]} {t(", ", lang).join(str(r["answer"]) for r in c["runs"] if r["answer"] is not None)}'
        for c in (eye or data["contenders"]) if any(r["answer"] is not None for r in c["runs"]))
    line = t("I counted {n} touches. Truth: {truth}. Models by eye (stills): {models}. Count it yourself: {url}"
             if eye else "I counted {n} touches. Truth: {truth}. Models: {models}. Count it yourself: {url}", lang)
    return line.format(n="{n}", truth=data["truth"], models=models, url=URLS[lang] + "#count")


def count_block(rows: list[dict], lang: str = "en", inner: str = "") -> str:
    """The "Count it yourself" block (`bench.count`): the task video, a count box, and a reveal with the truth, each
    contender's stored answers and the blind guess ('' when no contender ran the task). Without JavaScript the count
    box stays hidden and the reveal is a closed <details>; with it the reveal shows only after a count is entered.
    `inner` (the clip, which shows the answer) goes inside the reveal."""
    data = count_it.count_data(rows)
    if data is None:
        return ""
    up = "" if lang == "en" else "../"
    truth = data["truth"]
    items = [f'<li><span>{esc(c["label"])} <span class="kind">{t(c["track"] + " track", lang)}</span></span>'
             f'<span class="ans">{count_answers(c["runs"], truth)}</span></li>' for c in data["contenders"]]
    if data["floor"]:
        items.append(f'<li class="blind"><span>{t("Blind guess (no video seen)", lang)}</span>'
                     f'<span class="ans">{esc(data["floor"]["answer"])}</span></li>')
    lead = t("The {} task of {}: the same {} s video every contender got, with no answer drawn on it. Watch it, "
             "count, type your number; only then does the page show the truth and what each model answered.",
             lang).format(f"<code>{esc(data['task'])}</code>", esc(data["suite"]), f"{data['seconds']:g}")
    rule = t("How the bench scores a count: {}", lang).format(esc(t(KINDS[0][2], lang)))
    tracks = t("Frames track: the model saw stills of this video, one every {} s, and ran no code. Code track: it "
               "could write and run its own tracker. The blind guess copies the example in the task text.",
               lang).format(f"{count_it.STILL_S:g}")
    stored = t("Answers as stored in {}, one per run; exact ones in green; &ndash; = the run gave no answer.",
               lang).format(f'<a href="{RESULTS_URL}">benchmark/results</a>')
    you = t("You counted {n}: off by {d}, which the bench scores {s}.", lang)
    return (f'<section class="count" id="count" aria-labelledby="count-h" data-truth="{truth}" '
            f'data-you="{esc(you)}" data-line="{esc(share_line(data, lang))}" data-copied="{esc(t("Copied", lang))}">'
            f'<h2 id="count-h">{t("Count it yourself", lang)}</h2><p>{lead}</p>'
            f'<p>{t("The task text the contenders got:", lang)}</p>'
            f'<blockquote>{esc(t(data["question"], lang))}</blockquote>'
            f'<video src="{up}{count_it.MP4}" poster="{up}{count_it.POSTER}" controls muted playsinline '
            f'preload="none" width="640" height="360" aria-label="{esc(t(COUNT_VIDEO, lang))}"></video>'
            f'<form id="count-form" hidden><label for="count-n">{t("Your count", lang)}</label>'
            f'<input id="count-n" type="number" inputmode="numeric" min="0" max="999" step="1" required>'
            f'<button type="submit">{t("Show the answers", lang)}</button></form>'
            f'<details id="count-reveal"><summary>{esc(t(COUNT_OPEN, lang))}</summary>'
            f'<p class="truth"><strong>{t("Truth: {} touches", lang).format(truth)}</strong></p>'
            f'<p class="you" id="count-you" tabindex="-1" aria-live="polite" hidden></p>'
            f'<ul class="answers">{"".join(items)}</ul>'
            f'<p class="rule">{rule}</p><p class="rule">{tracks}</p><p class="rule">{stored}</p>'
            f'<div id="count-share" hidden><label for="count-line">{t("Your line to share", lang)}</label>'
            f'<textarea id="count-line" rows="3" readonly></textarea>'
            f'<button type="button" id="count-copy">{t("Copy", lang)}</button></div>{inner}</details>'
            f"<script>{COUNT_JS}</script></section>")


CARD_TITLE_ZH = "哪个编程 agent 最会看体育录像？"


def social(card: bool, lang: str = "en") -> str:
    """The link preview tags (Open Graph, X), as the landing page has them; og:image only when the card exists."""
    title = share_card.TITLE if lang == "en" else CARD_TITLE_ZH
    tags = [f'<meta property="og:title" content="{esc(title)}">',
            f'<meta property="og:description" content="{esc(t(WHAT, lang))}">']
    if card:   # one card for both pages (its text is English)
        tags += [f'<meta property="og:image" content="{PAGE_URL}{share_card.NAME}">',
                 f'<meta property="og:image:width" content="{share_card.SIZE[0]}">',
                 f'<meta property="og:image:height" content="{share_card.SIZE[1]}">']
    tags += [f'<meta property="og:url" content="{URLS[lang]}">',
             '<meta name="twitter:card" content="summary_large_image">']
    return "\n".join(tags)


def alternates(lang: str) -> str:
    """The canonical link and hreflang alternates, the same set on both pages (English is the x-default)."""
    links = [f'<link rel="canonical" href="{URLS[lang]}">']
    links += [f'<link rel="alternate" hreflang="{TAGS[x]}" href="{URLS[x]}">' for x in LANGS]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{URLS["en"]}">')
    return "\n".join(links)


def switch(lang: str) -> str:
    """The language switch link: to the Chinese page from the English one, and back."""
    if lang == "en":
        return '<a class="switch" href="zh/" hreflang="zh-CN" lang="zh-CN">中文</a>'
    return '<a class="switch" href="../" hreflang="en" lang="en">English</a>'


CLIP_ALT_ZH = ("短片：程序画的一段颠小球视频，接着是 agent 在一次快速连续两触前后看到的静帧（放大），最后是真实触球数和各个"
               "模型的回答。")


def clip_block(clip: bool, lang: str = "en") -> str:
    """The short clip at the top (`bench.clip`: one hard moment, then truth vs answers), when it was drawn."""
    if not clip:
        return ""
    up = "" if lang == "en" else "../"     # the Chinese page sits in zh/ and shows the same clip
    alt = share_clip.ALT if lang == "en" else CLIP_ALT_ZH
    caption = (f"One hard moment of {share_clip.SUITE} ({share_clip.TASK}, {share_clip.TRACK} track), then what each "
               "model answered, from the result files." if lang == "en" else
               f"{share_clip.SUITE} 里的一个难点（{share_clip.TASK}，{share_clip.TRACK} 赛道），然后是每个模型的回答，"
               "数据来自结果文件。短片里的文字是英文。")
    return (f'<figure style="margin:1rem 0"><video src="{up}{share_clip.MP4}" autoplay muted loop playsinline '
            f'preload="metadata" aria-label="{esc(alt)}" style="display:block;width:100%;max-width:'
            f'{share_clip.SIZE}px;height:auto;border-radius:10px"><img src="{up}{share_clip.GIF}" '
            f'alt="{esc(alt)}" style="width:100%;height:auto"></video>'
            f'<figcaption style="color:var(--muted);font-size:.9rem;margin-top:.3rem">{caption} '
            f'<a href="{up}{share_clip.GIF}">GIF</a> · <a href="{up}{share_clip.MP4}">MP4</a>'
            f'</figcaption></figure>')


def top_blocks(rows: list[dict], clip: bool, count: bool, lang: str = "en") -> str:
    """The count block (when its video was drawn) with the clip inside its reveal (the clip shows the answer), or the
    clip alone."""
    block = count_block(rows, lang, clip_block(clip, lang)) if count else ""
    return block or clip_block(clip, lang)


def render(rows: list[dict], notes: list[str], card: bool = False, clip: bool = False, lang: str = "en",
           count: bool = False, effort=()) -> str:
    """The page in `lang` ("en": index.html, "zh": zh/index.html); both show the same rows and numbers. `effort`:
    the languages whose effort chart was drawn."""
    if lang == "zh":
        return render_zh(rows, notes, card, clip, count, effort)
    code = [r for r in rows if track_of(r) == TRACK]
    board = boards(code) if any(not is_baseline(r) for r in code) else empty()
    runs = sum(1 for r in rows if not is_baseline(r))
    skipped = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        skipped = (f'<div class="note" role="note"><strong>{len(notes)} result file{"s" * (len(notes) > 1)} '
                   f"skipped</strong> (not shown in the table):<ul>{items}</ul></div>")
    kinds = "".join(f'<section><h3>{k}</h3><p>{esc(what)}</p><p class="rule">{esc(rule)}</p></section>'
                    for k, what, rule in KINDS)
    steps = "".join(f"<li>{esc(label)}<pre><code>{esc(cmd)}</code></pre></li>"
                    for label, cmd in COMMANDS) + presets_step()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{esc(WHAT)}">
{alternates("en")}
{social(card)}
<style>{CSS}</style>
</head>
<body>
<main>
<p class="name"><a href="../">sports-video-coach</a> {switch("en")}</p>
<h1>{TITLE}</h1>
<p class="lead">{esc(WHAT)}</p>
<p class="lead">{esc(PART_OF)} <a href="{DEMO_URL}">See a demo coaching page</a>.</p>
<ul class="chips"><li>Suites {", ".join(n for n, _ in SUITES)}</li><li>{runs} run{"s" * (runs != 1)}</li>
<li>Measured truth only</li>{latest(rows)}</ul>
{jump(rows)}
{top_blocks(rows, clip, count)}
{facts_block(rows)}

<h2 id="leaderboard">Leaderboard</h2>
<p>Code track: the agent may write and run its own tracker. The frames-only track, where the agent reviews by eye,
is <a href="#frames">further down</a>.</p>
{skipped}{board}

{frames_board(rows, effort=effort)}

<h2 id="method">Method</h2>
<p>The tasks are synthetic videos drawn by the tool, so the truth is exact: no human labels, no judge model.
The agent sees only the videos and writes its answers; <code>bench score</code> compares them with the truth.</p>
{prompt_block()}
<div class="cards">{kinds}</div>
<p>Total = the mean of the task scores. {esc(ABOVE)} Full rules: <a href="{DOC_URL}">docs/benchmark.md</a>.</p>

<h2 id="run">Run it yourself</h2>
<ol class="steps">{steps}</ol>

<h2 id="submit">Submit your run</h2>
<ul class="plain">
<li>Open a pull request that adds your result file to <code>benchmark/results/</code>.
CI re-scores it with <code>bench validate</code>.</li>
<li>No pull request? Paste the file into the <a href="{ISSUE_URL}">benchmark result issue form</a>.</li>
<li>Rules: do not read the truth files or the package source; one run = one file; report wall time honestly.</li>
</ul>

<h2 id="honesty">Honesty notes</h2>
<ul class="plain">
<li>The benchmark and this page were built with a coding agent (Claude Code).</li>
<li>Every row can be rerun: same suite, same command, scores recomputed from the stored answers. A rerun's answers
can differ (see the sample size note at the top).</li>
<li>The author wrote the tool, drew the suites and submitted the first runs; outside runs are welcome (above).</li>
<li>Failed and killed runs stay on the board and count in their contender's mean.</li>
<li>Synthetic drills test counting and timing, not every part of a coach's review.</li>
</ul>

<footer>Made by <a href="{REPO_URL}">sports-video-coach</a> (MIT).</footer>
</main>
</body>
</html>
"""


def render_zh(rows: list[dict], notes: list[str], card: bool = False, clip: bool = False, count: bool = False,
              effort=()) -> str:
    """The Chinese page (zh/index.html): the English page's sections, rows and numbers, in Chinese."""
    lang = "zh"
    code = [r for r in rows if track_of(r) == TRACK]
    board = boards(code, "", lang) if any(not is_baseline(r) for r in code) else empty(lang)
    runs = sum(1 for r in rows if not is_baseline(r))
    skipped = ""
    if notes:   # the notes name files and parse errors, so they stay as `load` wrote them
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        skipped = (f'<div class="note" role="note"><strong>{len(notes)} 个结果文件被跳过</strong>（不在表里）：'
                   f"<ul>{items}</ul></div>")
    kinds = "".join(f'<section><h3>{KIND_ZH[k]} <span class="kind">{k}</span></h3><p>{esc(t(what, lang))}</p>'
                    f'<p class="rule">{esc(t(rule, lang))}</p></section>' for k, what, rule in KINDS)
    steps = "".join(f"<li>{esc(t(label, lang))}<pre><code>{esc(cmd)}</code></pre></li>"
                    for label, cmd in COMMANDS) + presets_step(lang)
    title = t(TITLE, lang)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{esc(t(WHAT, lang))}">
{alternates(lang)}
{social(card, lang)}
<style>{CSS}</style>
</head>
<body>
<main>
<p class="name"><a href="../../">sports-video-coach</a> {switch(lang)}</p>
<h1>{title}</h1>
<p class="lead">{esc(t(WHAT, lang))}</p>
<p class="lead">{esc(t(PART_OF, lang))} <a href="{DEMO_URL}">看一个示例教练复盘页</a>。</p>
<ul class="chips"><li>套件 {", ".join(n for n, _ in SUITES)}</li><li>{runs} 次运行</li>
<li>只用测出来的真实值</li>{latest(rows, lang)}</ul>
{jump(rows, lang)}
{top_blocks(rows, clip, count, lang)}
{facts_block(rows, lang)}

<h2 id="leaderboard">排行榜</h2>
<p>代码赛道：agent 可以自己写追踪程序并运行。静帧赛道（agent 只用眼睛看）在<a href="#frames">下面</a>。
设置栏照搬结果文件里的英文原文。</p>
{skipped}{board}

{frames_board(rows, lang, effort)}

<h2 id="method">方法</h2>
<p>题目是工具画出来的合成视频，所以真实值是精确的：没有人工标注，也没有评审模型。
agent 只看得到视频，写下回答；<code>bench score</code> 把回答和真实值比对。</p>
{prompt_block(lang)}
<div class="cards">{kinds}</div>
<p>总分 = 各题分数的平均值。{esc(t(ABOVE, lang))} 完整规则：<a href="{DOC_URL}">docs/benchmark.md</a>（英文）。</p>

<h2 id="run">自己跑一遍</h2>
<ol class="steps">{steps}</ol>

<h2 id="submit">提交你的运行</h2>
<ul class="plain">
<li>开一个 pull request，把你的结果文件加到 <code>benchmark/results/</code>。
CI 会用 <code>bench validate</code> 重新打分。</li>
<li>不想开 pull request？把文件贴进<a href="{ISSUE_URL}">基准结果 issue 表单</a>。</li>
<li>规则：不读真实值文件，不读包的源码；一次运行 = 一个文件；如实报告实际用时。</li>
</ul>

<h2 id="honesty">诚实说明</h2>
<ul class="plain">
<li>这个基准测试和本页都是用编程 agent（Claude Code）做的，中文版也是。</li>
<li>每一行都能重跑：同样的套件、同样的命令，分数由存下的回答重新算出。重跑的回答可能不同（见页首的样本量说明）。</li>
<li>作者写了这个工具、画了套件、提交了最早的几次运行；欢迎外部提交（见上文）。</li>
<li>失败和被终止的运行留在榜上，计入该参赛者的平均分。</li>
<li>合成训练题测的是数数和计时，不是教练复盘的全部。</li>
</ul>

<footer>由 <a href="{REPO_URL}">sports-video-coach</a>（MIT）制作。</footer>
</main>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench page", description=__doc__.split("\n\n")[0])
    ap.add_argument("results_dir", help="folder of result files (benchmark/results)")
    ap.add_argument("out_dir", help="where to write index.html (and zh/index.html)")
    a = ap.parse_args(argv)
    rows, notes = load(Path(a.results_dir))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    card = share_card.write(rows, out)
    if card is None:
        print("[bench page] no share card: matplotlib is not installed (the page has no og:image)")
    clip = share_clip.write(rows, out)
    count = count_it.write(rows, out)
    effort = tuple(effort_chart.write(rows, out))
    if not effort and effort_chart.effort_data(rows)["groups"]:
        print("[bench page] no effort chart: matplotlib is not installed (the section is text only)")
    elif effort and "zh" not in effort:
        print("[bench page] effort chart in English only: no CJK font found (" + ", ".join(effort_chart.CJK_FONTS)
              + ")")
    if count is None:
        print("[bench page] no count-it-yourself block: needs ffmpeg and a run of the task")
    shown = (card is not None, clip is not None)
    (out / "index.html").write_text(render(rows, notes, *shown, count=count is not None, effort=effort), encoding="utf8")
    (out / "zh").mkdir(exist_ok=True)
    (out / "zh" / "index.html").write_text(render(rows, notes, *shown, "zh", count is not None, effort), encoding="utf8")
    for n in notes:
        print(f"[bench page] skipped {n}")
    runs = sum(1 for r in rows if not is_baseline(r))
    print(f"[bench page] {(out / 'index.html').as_posix()} and zh/index.html: {runs} run{'s' * (runs != 1)}, "
          f"{len(notes)} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
