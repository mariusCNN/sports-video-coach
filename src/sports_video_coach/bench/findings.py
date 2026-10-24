"""The benchmark's findings page: `<out_dir>/findings/index.html` and its Chinese twin `<out_dir>/zh/findings/`,
written by `bench page` next to the leaderboard. A short article for readers and search engines: each finding is
a question, a one-line answer, the measured numbers, links to the board rows and transcripts, and what bounds it
(how many runs). Every number comes from `benchmark/results` through the leaderboard's own functions (`load`,
`summarize`, `seed_floor`, `above_value`, `fails`, `effort.effort_data`); `findings_data` is the data step (tested),
`render` only formats it. A finding whose data is missing is left out, so an empty results folder gives a short
"no runs yet" page.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import card as share_card
from . import effort as effort_chart
from . import page as P

BOARD = effort_chart.SUITE + P.FRESH   # the fresh-seed frames board: unseen seeds, review by eye
FIXED = effort_chart.SUITE             # the fixed svc-bench-3 frames board
TRACK = "frames"
LOCAL = ("Ollama",)                    # agents that run a model on the runner's own GPU
BIG = 0.2                              # a gap in mean above chance the answers call large
LOW = 0.05                             # a best above chance the local answer calls "not for this"
TOP = 0.99                             # "near perfect" mean above chance, for the cost finding
URLS = {"en": f"{P.PAGE_URL}findings/", "zh": f"{P.PAGE_URL}zh/findings/"}
SUITE_ORDER = [n for n, _ in P.SUITES]

TITLE = "Can a coding agent review sports film? What the benchmark measured"
DESC = ("Findings from a sports film review benchmark with exact ground truth: what reasoning effort changed, why "
        "raw scores mislead, whether agents can count reps from video, and whether a small local vision model is "
        "good enough. Every number is computed from the result files.")
LEAD = ("Short answers from the sports film review benchmark. The videos are drawn by the tool, so the truth is "
        "exact and every number below is measured, not judged. Each finding links to the board rows it comes from.")
ABOVE_NOTE = ("Above chance: 0 = no better than a blind guess that sees no video, 1 = perfect "
              "(per task, (score - floor) / (1 - floor)).")
NOT_SHOWN = (
    "The videos are synthetic drawn drills, not real game film: they test counting and timing by eye, not a "
    "coach's whole review.",
    "Few runs: most settings ran once or twice, so small gaps can be noise.",
    "Settings are not equalised across agents; each row ran with the flags its Settings column names.",
    "The author wrote the tool, drew the suites and submitted these runs; no outside runs yet.",
)
EFFORT_HOW = ("Same model, svc-bench-3 drawn from a new seed for every run, frames track (stills only, no code); "
              "only the effort setting changed.")
CODE_HOW = ("Code track: the agent writes and runs its own tracker. The drawn videos have flat colours, so a "
            "pixel tracker finds the ball; that is why the frames track exists.")
COST_HOW = ("Cost is what the agent itself reported (Claude Code does, Codex and Ollama do not); time is wall "
            "seconds.")
LOCAL_HOW = "Run through Ollama on the runner's own GPU, one request per task with that task's contact sheets."
FAILS_HOW = ("Mean recomputed score per task (0 to 1) on the fresh-seed board; the board's fold lists every answer "
             "and what was missed.")
BUILT = ("This page, the benchmark and its leaderboard were built with a coding agent (Claude Code); the numbers "
         "are filled in from the result files each time the site is built.")

# The Chinese page: every English text, keyed by itself; `t` raises KeyError on a missing entry (a test renders zh).
RUN_FLOORS = "Each run's blind guess on its own seed"
BOARDS_NOTE = ("Unless a finding names another board, the numbers below come from the fresh-seed board, where "
               "svc-bench-3 is drawn from a new seed for every run. The fixed {} board has different figures for the "
               "same contenders: {} is {} above chance there and {} here.")
ZH = {
    TITLE: "编程 agent 能看懂体育录像吗？基准测试测出了什么",
    DESC: "一个有精确真实值的体育录像复盘基准测试的结论：effort 改变了什么、为什么原始分会误导、agent 能不能从视频里数"
          "次数、本地小视觉模型够不够用。每个数字都从结果文件算出。",
    LEAD: "体育录像复盘基准测试的简短结论。视频是工具画出来的，所以真实值是精确的，下面每个数字都是测出来的，不是评出来"
          "的。每条结论都链接到它来自的榜单行。",
    ABOVE_NOTE: "超出盲猜：0 = 不比不看视频的盲猜强，1 = 满分（每道题算 (score - floor) / (1 - floor)）。",
    NOT_SHOWN[0]: "视频是程序画的合成训练题，不是真实比赛录像：测的是用眼睛数数和计时，不是教练复盘的全部。",
    NOT_SHOWN[1]: "运行次数少：大多数设置只跑了一两次，小差距可能是噪声。",
    NOT_SHOWN[2]: "各 agent 的设置没有统一；每一行按它设置栏写的参数运行。",
    NOT_SHOWN[3]: "作者写了这个工具、画了套件、提交了这些运行；还没有外部提交的运行。",
    BUILT: "本页、这个基准测试和排行榜都是用编程 agent（Claude Code）做的；每次构建网站时，数字都从结果文件重新填入。",
    "Benchmark findings": "基准测试结论", "Leaderboard": "排行榜", "Latest result {}": "最新结果 {}",
    "{} runs": "{} 次运行", "No runs yet, so no findings yet.": "还没有运行记录，所以还没有结论。",
    "Board rows": "榜单行", "Transcripts": "对话记录", "Bound:": "边界：", "Answer:": "回答：",
    "What this benchmark does not show": "这个基准测试说明不了什么", "Rerun it yourself": "自己重跑",
    "Run any row again with one command: {}. Run an agent we have not tested and send the row: {}.":
        "一条命令就能重跑任意一行：{}。跑一个我们没测过的 agent，把结果发来：{}。",
    "the rerun section": "重跑说明", "issue #7": "issue #7", "Before you trust this": "信之前先看",
    "Contender": "参赛者", "Setting": "设置", "Runs": "次数", "Above chance": "超出盲猜", "Time per run": "每次用时",
    "Cost per run": "每次费用", "Total": "总分", "Suite": "套件", "Blind guess total": "盲猜总分",
    "Board": "榜单", "Code-track runs": "代码赛道运行", "Scored 1.0": "满分 1.0", "Lowest total": "最低总分",
    "Blind guess on the same videos": "同一批视频上的盲猜", "fresh seeds": "新种子", "-": "-",
    "default effort": "默认 effort", "effort {}": "effort {}", "{} of {}": "{1} 次中有 {0} 次",
    "not recorded": "没有记录", "no answer": "没有回答", "Task": "题目",
    # the two svc-bench-3 boards
    BOARDS_NOTE: "除非某条结论写明别的榜，下面的数字都来自新种子榜：每次运行都用新种子重新生成 svc-bench-3。固定的 {} 榜上"
                 "同样这些参赛者的数字不同：{} 在那里超出盲猜 {}，在这里是 {}。",
    # effort
    "Likely, on few runs.": "可能有，但运行次数少。",
    " Changing only the effort moved {} from {} ({}, n={}) to {} ({}, n={}) above chance.":
        "只改 effort，{} 的超出盲猜分就从 {}（{}，n={}）变到 {}（{}，n={}）。",
    "Does reasoning effort matter for video review?": "effort 对看录像有影响吗？",
    "Yes, a lot.": "有，而且很大。", "A little.": "有一点。",
    " At {} it gave no answer before the time limit.": "用 {} 时，它在时限前没有给出回答。",
    EFFORT_HOW: "同一模型，每次运行都用新种子重新生成 svc-bench-3，静帧赛道（只看静帧，不跑代码）；只改了 "
                               "effort 设置。",
    "{} runs in all, each on its own seed; {} of {} settings ran once. A measured difference, not a variance "
    "estimate.": "一共 {0} 次运行，各用自己的种子；{2} 个设置中有 {1} 个只跑了一次。这是测出来的差别，不是方差估计。",
    "killed at {}": "到 {} 被终止",
    # floor
    "Does a raw score tell you how well a model sees?": "原始分能说明模型看得多准吗？",
    "Not by itself. A blind guess that sees no video already totals {}–{}, so read the above-chance column: {} "
    "totals {} but is only {} above chance.":
        "单看说明不了什么。不看视频的盲猜总分就有 {}–{}，所以要看超出盲猜那一栏：{} 总分 {}，超出盲猜只有 {}。",
    "The blind guess copies the example answers in the task text. On fresh seeds each run has its own floor; "
    "those {} floors total {}–{}.": "盲猜照抄题目里的示例答案。新种子上每次运行有自己的基线；这 {} 个基线的总分是 {}–{}。",
    RUN_FLOORS: "每次运行在自己种子上的盲猜", "Seed": "种子",
    "Floors are computed by the tool for every suite and seed; one blind guess per suite, no randomness.":
        "基线由工具为每个套件和种子算出；每个套件一个盲猜，没有随机性。",
    # code track
    "Can a coding agent count reps from video?": "编程 agent 能从视频里数次数吗？",
    "On these drawn drills, yes, when it may run code: {} of {} code-track runs scored 1.0 and none totalled below "
    "{}. On the frames track, by eye from stills, contenders spread from {} to {} above chance.":
        "在这些程序画的训练题上，能，只要允许它运行代码：代码赛道 {1} 次运行中有 {0} 次满分 1.0，最低总分 {2}。在静帧赛道"
        "只用眼睛看静帧，各参赛者的超出盲猜分从 {3} 到 {4} 不等。",
    CODE_HOW: "代码赛道：agent 自己写追踪程序并运行。画出来的视频颜色单"
                                                            "一，像素追踪就能找到球；这也是设静帧赛道的原因。",
    "{} code-track runs over {} suites; the frames range is the contenders' mean above chance on the fresh-seed "
    "board.": "{} 次代码赛道运行，覆盖 {} 个套件；静帧的范围是新种子榜上各参赛者的平均超出盲猜分。",
    # local model
    "Is a small local vision model good enough?": "本地小视觉模型够用吗？",
    "Not for this:": "做这个不够：", "Unclear:": "看不清：",
    " {} scored {} above chance on every board it ran: totals of {} against blind guesses of {}.":
        "{} 在它跑过的每个榜上超出盲猜分都是 {}：总分 {}，而盲猜是 {}。",
    ", ": "，", " and ": " 和 ",
    LOCAL_HOW:
        "通过 Ollama 在运行者自己的显卡上跑，每道题发一次请求，附上那道题的缩略图。",
    "{} runs of one quantised model at temperature 0; a larger local model may do better.":
        "同一个量化模型跑了 {} 次，temperature 0；更大的本地模型可能更好。",
    # cost
    "What does a near-perfect review cost?": "接近满分的复盘要花多少？",
    "On the fresh-seed board, of the contenders at {} or more above chance with a recorded cost, the cheapest was {}: "
    "{} and {} per run ({}), scoring {} above chance.":
        "新种子榜上，超出盲猜 {} 及以上、有费用记录的参赛者里最便宜的是 {}：每次 {}、{}（{}），超出盲猜 {}。",
    " {} also reached {} but reports no cost.": "{} 也达到了 {}，但没有报告费用。",
    "Not run on fresh seeds: {}.": "没在新种子上跑过的：{}。",
    "{} on the fixed {} board: {} above chance over {}{}, {} per run": "{0} 在固定的 {1} 榜上：{3}，超出盲猜 {2}{4}，每次 {5}",
    " (best {})": "（最好 {}）", " ({})": "（{}）",
    "one run": "1 次运行",
    " {} cost {} per run, scoring {} above chance.": "{} 每次 {}，超出盲猜 {}。",
    COST_HOW:
        "费用是 agent 自己报告的数（Claude Code 会报，Codex 和 Ollama 不报）；用时是实际秒数。",
    "Means over {} runs; most contenders ran once or twice. Prices are per run of four short videos.":
        "{} 次运行的平均值；大多数参赛者只跑了一两次。价格按每次运行（四段短视频）算。",
    # fails
    "Where does each model fail?": "每个模型错在哪里？",
    "The hardest task was {}: a mean score of {} over the {} runs that answered. {}":
        "最难的一题是 {0}：给出回答的 {2} 次运行平均得分 {1}。{3}",
    FAILS_HOW: "新种子榜上每道题重新算出的平均分（0 到 1）；榜上的折叠块列出每个回答和漏掉了什么。",
    "Scores recomputed from each run's stored answer and its seed's truth; {} runs.":
        "分数由每次运行存下的回答和它那个种子的真实值重新算出；{} 次运行。",
}

TASK_WHAT = {   # what each svc-bench-3 task asks, for the hardest-task line
    "juggle-touches": "count one player's touches while a second player juggles next to them",
    "far-hoop-shots": "made or missed at a 16 px wide far rim",
    "pass-releases": "when each pass leaves the hand, with pass fakes",
    "stroke-rate": "a rowing stroke rate, with a far boat at a close rate",
}
ZH.update({
    TASK_WHAT["juggle-touches"]: "旁边还有一个人在颠球时，数其中一人的触球次数",
    TASK_WHAT["far-hoop-shots"]: "在 16 px 宽的远处篮筐上判断进没进",
    TASK_WHAT["pass-releases"]: "每次传球什么时候出手，中间有传球假动作",
    TASK_WHAT["stroke-rate"]: "划船的划桨节奏，远处有一条节奏相近的船",
    "({})": "（{}）",
})


def t(en: str, lang: str) -> str:
    return en if lang == "en" else ZH[en]


def board_rows(rows: list[dict], suite: str, track: str) -> list[dict]:
    return [r for r in rows if P.suite_of(r) == suite and P.track_of(r) == track]


def floor_scores(floor_row: dict | None) -> dict | None:
    return {str(x["id"]): x.get("score") for x in floor_row["tasks"]} if floor_row else None


def floor_total(r: dict, floor_row: dict | None) -> float | None:
    """The blind guess's total on a run's videos: its own seed's floor, else the board's floor row."""
    if r.get("seed") is not None:
        f = P.seed_floor(str(r.get("suite") or P.SUITE), P.track_of(r), r["seed"])
        return sum(f.values()) / len(f) if f else None
    return float(floor_row["total"]) if floor_row else None


def contender(key: tuple[str, str, str]) -> dict:
    agent, model, settings = key
    return {"agent": agent, "model": effort_chart.model_label(model, agent),
            "effort": effort_chart.effort_of(settings)}


def ident(key: tuple[str, str, str]) -> tuple[str, str, str]:
    """A contender across boards: agent, model and effort (other settings text differs between the boards)."""
    c = contender(key)
    return c["agent"], c["model"], c["effort"]


def fixed_finding(rows: list[dict]) -> dict | None:
    """The fixed svc-bench-3 frames board next to the fresh one: the shared contender whose above chance differs
    most, and the fixed board's contenders that never ran on fresh seeds."""
    fixed = board_rows(rows, FIXED, TRACK)
    fresh = board_rows(rows, BOARD, TRACK)
    a = {ident(x["key"]): x for x in P.summarize(fixed, P.floor_of(fixed)) if x["above"] is not None}
    b = {ident(x["key"]): x for x in P.summarize(fresh) if x["above"] is not None}
    if not a or not b:
        return None
    shared = [k for k in a if k in b]
    diff = max(shared, key=lambda k: (abs(a[k]["above"] - b[k]["above"]), k), default=None)
    return {"diff": {"fixed": a[diff], "fresh": b[diff]} if diff else None,
            "missing": [a[k] for k in a if k not in b]}


def effort_finding(rows: list[dict]) -> dict | None:
    """The effort data, plus the bar pair with the widest gap in one contender (answered bars only)."""
    data = effort_chart.effort_data(rows)
    best = None
    for g in data["groups"]:
        answered = [b for b in g["bars"] if b["above"] is not None and b["n"] > b["no_answer"]]
        if len(answered) < 2:
            continue
        lo, hi = min(answered, key=lambda b: b["above"]), max(answered, key=lambda b: b["above"])
        if best is None or hi["above"] - lo["above"] > best["gap"]:
            best = {"label": g["label"], "lo": lo, "hi": hi, "gap": round(hi["above"] - lo["above"], 3),
                    "silent": [b for b in g["bars"] if b["n"] == b["no_answer"]]}
    if best is None:
        return None
    bars = [b for g in data["groups"] for b in g["bars"]]
    return {"data": data, "best": best, "runs": sum(b["n"] for b in bars),
            "singles": sum(1 for b in bars if b["n"] == 1), "settings": len(bars)}


def floor_finding(rows: list[dict]) -> dict | None:
    """Each suite's blind-guess total, the fresh seeds' floor totals, and the board contender whose raw total
    overstates it most (largest total minus above chance)."""
    suites = []
    for s in SUITE_ORDER:
        f = P.floor_of(board_rows(rows, s, TRACK))
        if f:
            suites.append({"suite": s, "total": float(f["total"])})
    mine = board_rows(rows, BOARD, TRACK)
    summary = [x for x in P.summarize(mine) if x["above"] is not None]
    if not suites or not summary:
        return None
    seeds = [{"key": P.contender_key(r), "seed": r["seed"], "floor": v, "file": r["_file"]}
             for r in mine if not P.is_baseline(r) for v in [floor_total(r, None)] if v is not None]
    worst = max(summary, key=lambda x: (round(x["total"] - x["above"], 6), x["key"]))
    totals = [x["total"] for x in suites] + [x["floor"] for x in seeds]
    return {"suites": suites, "seeds": seeds, "lo": min(totals), "hi": max(totals), "summary": summary,
            "worst": worst}


def code_finding(rows: list[dict]) -> dict | None:
    """Per code-track board: runs, how many scored 1.0 and the lowest total; and the frames board's spread."""
    boards = []
    for s in SUITE_ORDER:
        runs = [r for r in board_rows(rows, s, P.TRACK) if not P.is_baseline(r)]
        if runs:
            totals = [float(r["total"]) for r in runs]
            boards.append({"suite": s, "n": len(runs), "ones": sum(1 for v in totals if v == 1), "lo": min(totals)})
    summary = [x for x in P.summarize(board_rows(rows, BOARD, TRACK)) if x["above"] is not None]
    if not boards or not summary:
        return None
    return {"boards": boards, "n": sum(b["n"] for b in boards), "ones": sum(b["ones"] for b in boards),
            "lo": min(b["lo"] for b in boards), "frames_lo": min(x["above"] for x in summary),
            "frames_hi": max(x["above"] for x in summary)}


def local_finding(rows: list[dict]) -> dict | None:
    """Every frames-track run of a local model (LOCAL agents): its board, total, blind-guess total, above chance."""
    out = []
    names = SUITE_ORDER + [n + P.FRESH for n in SUITE_ORDER]
    for r in rows:
        if P.is_baseline(r) or P.track_of(r) != TRACK or r["contender"].get("agent") not in LOCAL:
            continue
        floor_row = P.floor_of(board_rows(rows, P.suite_of(r), TRACK))
        out.append({"file": r["_file"], "board": P.suite_of(r), "model": str(r["contender"].get("model") or ""),
                    "agent": r["contender"]["agent"], "total": float(r["total"]),
                    "floor": floor_total(r, floor_row), "above": P.above_value(r, floor_scores(floor_row)),
                    "secs": r.get("wall_seconds"), "evidence": r.get("evidence") or ""})
    out.sort(key=lambda x: (names.index(x["board"]) if x["board"] in names else len(names), x["file"]))
    return {"runs": out} if out else None


def cost_finding(rows: list[dict]) -> dict | None:
    """The fresh board's contenders with their mean time and cost; the cheapest one at TOP or more above chance and
    the dearest one there."""
    summary = [x for x in P.summarize(board_rows(rows, BOARD, TRACK)) if x["above"] is not None]
    top = [x for x in summary if x["above"] >= TOP and x["cost"] is not None]
    if not top:
        return None
    return {"summary": summary, "cheap": min(top, key=lambda x: (x["cost"], x["key"])),
            "dear": max(top, key=lambda x: (x["cost"], x["key"])), "runs": sum(x["n"] for x in summary),
            "unpriced": [x for x in summary if x["above"] >= TOP and x["cost"] is None]}


def fails_finding(rows: list[dict]) -> dict | None:
    """Mean recomputed score per task and contender on the fresh board (`page.fails`), and the hardest task."""
    mine = [r for r in board_rows(rows, BOARD, TRACK) if not P.is_baseline(r)]
    tasks = P.fails(mine, BOARD)
    if not tasks:
        return None
    to = P.merge_notes(sorted({P.contender_key(r) for r in mine}))
    of = {r["_file"]: to[P.contender_key(r)] for r in mine}
    order = [x["key"] for x in P.summarize(mine)]
    cells: dict[tuple, dict[str, list[float]]] = {}
    every: dict[str, list[float]] = {}     # the hardest task is judged on runs that answered at all
    silent = {r["_file"] for r in mine if effort_chart.no_answer(r)}
    for task in tasks:
        for x in task["runs"]:
            if x["score"] is None:
                continue
            cells.setdefault(of[x["file"]], {}).setdefault(task["id"], []).append(x["score"])
            if x["file"] not in silent:
                every.setdefault(task["id"], []).append(x["score"])
    ids = [task["id"] for task in tasks]
    table = [{"key": k, "scores": {i: round(sum(v) / len(v), 3) for i, v in cells[k].items()}}
             for k in order if k in cells]
    hard = min(every, key=lambda i: (sum(every[i]) / len(every[i]), ids.index(i)))
    return {"ids": ids, "table": table, "hard": hard, "hard_mean": round(sum(every[hard]) / len(every[hard]), 3),
            "hard_n": len(every[hard]), "runs": len(mine)}


def findings_data(rows: list[dict]) -> dict:
    """Everything the page shows, each finding None when its data is missing."""
    dates = [str(r.get("date")) for r in rows if r.get("date")]
    runs = sum(1 for r in rows if not P.is_baseline(r))
    return {"date": max(dates) if dates else "", "runs": runs,
            "evidence": {r["_file"]: r.get("evidence") or "" for r in rows},
            "effort": effort_finding(rows), "floor": floor_finding(rows), "code": code_finding(rows),
            "local": local_finding(rows), "cost": cost_finding(rows), "fails": fails_finding(rows),
            "fixed": fixed_finding(rows)}


# ---- rendering -------------------------------------------------------------------------------------------------

def esc(v) -> str:
    return P.esc(v)


def join(items: list[str], lang: str) -> str:
    """'a', 'a and b', 'a, b and c'."""
    if len(items) < 2:
        return "".join(items)
    return t(", ", lang).join(items[:-1]) + t(" and ", lang) + items[-1]


def n3(v) -> str:
    return "-" if v is None else f"{v:.3f}"


def name(key: tuple[str, str, str], lang: str) -> str:
    """'Sonnet 5.5, effort high' for a contender key (the effort only when its settings name one)."""
    c = contender(key)
    return c["model"] + ("" if c["effort"] == effort_chart.DEFAULT else
                         t(", ", lang) + effort_chart.setting(c["effort"], lang))


def agent_cell(key: tuple[str, str, str], lang: str) -> str:
    return f'<td>{esc(name(key, lang))} <span class="sub">{esc(key[0])}</span></td>'


def links(board_href: list[tuple[str, str]], files: list[str], evidence: dict, lang: str) -> str:
    """The row of links under a finding: board anchors on the leaderboard, then numbered transcripts."""
    parts = [f'<a href="../{h}">{esc(x)}</a>' for h, x in board_href]
    urls = [evidence.get(f, "") for f in files]
    urls = [u for u in urls if u.startswith("https://")]
    if urls:
        parts.append(esc(t("Transcripts", lang)) + " " + " ".join(
            f'<a href="{esc(u)}" rel="nofollow noopener">{i}</a>' for i, u in enumerate(urls, 1)))
    return f'<p class="links">{t("Board rows", lang)}: {" · ".join(parts)}</p>'


def section(fid: str, q: str, answer: str, body: str, foot: str, bound: str, lang: str) -> str:
    return (f'<section class="finding" id="{fid}"><h2>{esc(t(q, lang))}</h2>'
            f'<p class="answer"><strong>{t("Answer:", lang)}</strong> {answer}</p>{body}{foot}'
            f'<p class="bound"><strong>{t("Bound:", lang)}</strong> {bound}</p></section>')


NUM = ' class="num"'


def scroll(head: list[str], body: list[str]) -> str:
    th = "".join(f'<th scope="col"{NUM if i else ""}>{h}</th>' for i, h in enumerate(head))
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def board_label(board: str, lang: str) -> str:
    return board.removesuffix(P.FRESH) + (f" {t('({})', lang).format(t('fresh seeds', lang))}"
                                          if board.endswith(P.FRESH) else "")


def effort_section(f: dict, ev: dict, lang: str) -> str:
    b = f["best"]
    s = effort_chart.setting
    # a strong word only when the gap is large and every compared bar has at least two runs
    verdict = ("A little." if b["gap"] < BIG else "Yes, a lot." if min(b["lo"]["n"], b["hi"]["n"]) >= 2
               else "Likely, on few runs.")
    answer = t(verdict, lang) + t(
        " Changing only the effort moved {} from {} ({}, n={}) to {} ({}, n={}) above chance.", lang).format(
        esc(b["label"]), n3(b["lo"]["above"]), esc(s(b["lo"]["effort"], lang)), b["lo"]["n"], n3(b["hi"]["above"]),
        esc(s(b["hi"]["effort"], lang)), b["hi"]["n"])
    for x in b["silent"]:
        answer += t(" At {} it gave no answer before the time limit.", lang).format(esc(s(x["effort"], lang)))
    rows = []
    for g in f["data"]["groups"]:
        for x in g["bars"]:
            silent = x["n"] == x["no_answer"]
            above = (t("no answer", lang) + (" " + t("({})", lang).format(
                t("killed at {}", lang).format(effort_chart.limits_word(x, lang))) if x["timed_out"] else "")
                if silent else n3(x["above"]))
            secs = P.wall(x["secs"]) if x["secs"] is not None else "-"
            rows.append(f'<tr><td>{esc(g["label"])} <span class="sub">{esc(g["agent"])}</span></td>'
                        f'<td class="num">{esc(s(x["effort"], lang))}</td><td class="num">{x["n"]}</td>'
                        f'<td class="num above">{esc(above)}</td><td class="num">{secs}</td></tr>')
    head = [t(k, lang) for k in ("Contender", "Setting", "Runs", "Above chance", "Time per run")]
    files = [fl for g in f["data"]["groups"] for x in g["bars"] for fl in x["files"]]
    body = (f"<p>{esc(t(EFFORT_HOW, lang))}</p>" + scroll(head, rows))
    foot = links([(f"#{effort_chart.ANCHOR}", P.t("What effort changed", lang)),
                  (f"#frames-{BOARD}", board_label(BOARD, lang))], files, ev, lang)
    bound = esc(t("{} runs in all, each on its own seed; {} of {} settings ran once. A measured difference, not a "
                  "variance estimate.", lang).format(f["runs"], f["singles"], f["settings"]))
    return section("effort", "Does reasoning effort matter for video review?", answer, body, foot, bound, lang)


def floor_section(f: dict, lang: str) -> str:
    w = f["worst"]
    answer = t("Not by itself. A blind guess that sees no video already totals {}–{}, so read the above-chance "
               "column: {} totals {} but is only {} above chance.", lang).format(
        n3(f["lo"]), n3(f["hi"]), esc(name(w["key"], lang)), n3(w["total"]), n3(w["above"]))
    chips = "".join(f"<li>{esc(x['suite'])}: <strong>{n3(x['total'])}</strong></li>" for x in f["suites"])
    rows = [f'<tr>{agent_cell(x["key"], lang)}<td class="num">{x["n"]}</td><td class="num">{n3(x["total"])}</td>'
            f'<td class="num above">{n3(x["above"])}</td></tr>' for x in f["summary"]]
    head = [t(k, lang) for k in ("Contender", "Runs", "Total", "Above chance")]
    floors = [x["floor"] for x in f["seeds"]]
    seeds = (t("The blind guess copies the example answers in the task text. On fresh seeds each run has its own "
               "floor; those {} floors total {}–{}.", lang).format(len(floors), n3(min(floors)), n3(max(floors)))
             if floors else "")
    fold = ""
    if f["seeds"]:   # every per-seed floor the page quotes, so a reader can check the range
        cells = [f'<tr>{agent_cell(x["key"], lang)}<td class="num">{esc(x["seed"])}</td>'
                 f'<td class="num">{n3(x["floor"])}</td></tr>' for x in sorted(f["seeds"], key=lambda x: x["floor"])]
        fold = (f'<details class="fold"><summary>{esc(t(RUN_FLOORS, lang))}</summary>'
                + scroll([t(k, lang) for k in ("Contender", "Seed", "Blind guess total")], cells) + "</details>")
    body = (f'<p>{esc(t("Blind guess total", lang))}:</p><ul class="chips">{chips}</ul><p>{esc(seeds)}</p>{fold}'
            + scroll(head, rows) + f'<p class="sub">{esc(t(ABOVE_NOTE, lang))}</p>')
    foot = links([(f"#frames-{BOARD}", board_label(BOARD, lang)), ("#facts", t("Before you trust this", lang))],
                 [], {}, lang)
    bound = esc(t("Floors are computed by the tool for every suite and seed; one blind guess per suite, no "
                  "randomness.", lang))
    return section("floor", "Does a raw score tell you how well a model sees?", answer, body, foot, bound, lang)


def code_section(f: dict, lang: str) -> str:
    answer = t("On these drawn drills, yes, when it may run code: {} of {} code-track runs scored 1.0 and none "
               "totalled below {}. On the frames track, by eye from stills, contenders spread from {} to {} above chance.",
               lang).format(f["ones"], f["n"], n3(f["lo"]), n3(f["frames_lo"]), n3(f["frames_hi"]))
    rows = [f'<tr><td>{esc(b["suite"])}</td><td class="num">{b["n"]}</td><td class="num">{b["ones"]}</td>'
            f'<td class="num total">{n3(b["lo"])}</td></tr>' for b in f["boards"]]
    head = [t(k, lang) for k in ("Suite", "Code-track runs", "Scored 1.0", "Lowest total")]
    body = (f"<p>{esc(t(CODE_HOW, lang))}</p>"
            + scroll(head, rows))
    foot = links([(f"#{b['suite']}", b["suite"]) for b in f["boards"]] + [(f"#frames-{BOARD}", board_label(BOARD, lang))],
                 [], {}, lang)
    bound = esc(t("{} code-track runs over {} suites; the frames range is the contenders' mean above chance on the "
                  "fresh-seed board.", lang).format(f["n"], len(f["boards"])))
    return section("code", "Can a coding agent count reps from video?", answer, body, foot, bound, lang)


def local_section(f: dict, ev: dict, lang: str) -> str:
    runs = f["runs"]
    above = sorted({n3(x["above"]) for x in runs})
    best = max(x["above"] for x in runs)
    answer = t("Not for this:" if best < LOW else "Unclear:", lang) + t(
        " {} scored {} above chance on every board it ran: totals of {} against blind guesses of {}.", lang).format(
        esc(runs[0]["model"]), join(above, lang), join([n3(x["total"]) for x in runs], lang),
        join([n3(x["floor"]) for x in runs], lang))
    rows = [f'<tr><td>{esc(board_label(x["board"], lang))}</td><td class="num">{n3(x["total"])}</td>'
            f'<td class="num">{n3(x["floor"])}</td><td class="num above">{n3(x["above"])}</td>'
            f'<td class="num">{P.wall(float(x["secs"])) if P.is_num_value(x["secs"]) else "-"}</td></tr>' for x in runs]
    head = [t(k, lang) for k in ("Board", "Total", "Blind guess on the same videos", "Above chance", "Time per run")]
    body = f"<p>{esc(t(LOCAL_HOW, lang))}</p>" + scroll(head, rows)
    foot = links([(f"#frames-{b}", board_label(b, lang)) for b in dict.fromkeys(x["board"] for x in runs)],
                 [x["file"] for x in runs], ev, lang)
    bound = esc(t("{} runs of one quantised model at temperature 0; a larger local model may do better.",
                  lang).format(len(runs)))
    return section("local", "Is a small local vision model good enough?", answer, body, foot, bound, lang)


def cost_cell(x: dict, lang: str) -> str:
    if x["cost"] is None:
        return f'<td class="num sub">{esc(t("not recorded", lang))}</td>'
    part = (f' <span class="sub">{esc(t("({})", lang).format(t("{} of {}", lang).format(x["n_cost"], x["n"])))}'
            "</span>" if x["n_cost"] < x["n"] else "")
    return f'<td class="num">{P.usd(x["cost"])}{part}</td>'


def missing_line(fixed: dict | None, lang: str) -> str:
    """The fixed board's contenders that never ran on fresh seeds, with their cost there."""
    if not fixed or not fixed["missing"]:
        return ""
    items = [t("{} on the fixed {} board: {} above chance over {}{}, {} per run", lang).format(
                 name(x["key"], lang), FIXED, n3(x["above"]),
                 t("one run", lang) if x["n"] == 1 else t("{} runs", lang).format(x["n"]),
                 t(" (best {})", lang).format(n3(x["hi"])) if x["n"] > 1 and x["hi"] != x["above"] else "",
                 (P.usd(x["cost"]) + (t(" ({})", lang).format(t("{} of {}", lang).format(x["n_cost"], x["n"]))
                                      if x["n_cost"] < x["n"] else "")) if x["cost"] is not None
                 else t("not recorded", lang))
             for x in fixed["missing"]]
    return f'<p>{esc(t("Not run on fresh seeds: {}.", lang).format(join(items, lang)))}</p>'


def cost_section(f: dict, lang: str, fixed: dict | None = None) -> str:
    c, d = f["cheap"], f["dear"]
    answer = t("On the fresh-seed board, of the contenders at {} or more above chance with a recorded cost, the "
               "cheapest was {}: {} and {} per run ({}), scoring {} above chance.", lang).format(
        f"{TOP:g}", esc(name(c["key"], lang)), P.usd(c["cost"]), P.wall(c["secs"]),
        t("one run", lang) if c["n"] == 1 else t("{} runs", lang).format(c["n"]), n3(c["above"]))
    if d is not c:
        answer += t(" {} cost {} per run, scoring {} above chance.", lang).format(esc(name(d["key"], lang)), P.usd(d["cost"]),
                                                               n3(d["above"]))
    for x in f["unpriced"]:
        answer += t(" {} also reached {} but reports no cost.", lang).format(esc(name(x["key"], lang)), n3(x["above"]))
    rows = [f'<tr>{agent_cell(x["key"], lang)}<td class="num">{x["n"]}</td>'
            f'<td class="num above">{n3(x["above"])}</td>'
            f'<td class="num">{P.wall(x["secs"]) if x["secs"] is not None else "-"}</td>{cost_cell(x, lang)}</tr>'
            for x in f["summary"]]
    head = [t(k, lang) for k in ("Contender", "Runs", "Above chance", "Time per run", "Cost per run")]
    body = f"<p>{esc(t(COST_HOW, lang))}</p>" + scroll(head, rows) + missing_line(fixed, lang)
    foot = links([(f"#frames-{BOARD}", board_label(BOARD, lang))]
                 + ([(f"#frames-{FIXED}", FIXED)] if fixed and fixed["missing"] else []), [], {}, lang)
    bound = esc(t("Means over {} runs; most contenders ran once or twice. Prices are per run of four short videos.",
                  lang).format(f["runs"]))
    return section("cost", "What does a near-perfect review cost?", answer, body, foot, bound, lang)


def fails_section(f: dict, lang: str) -> str:
    what = TASK_WHAT.get(f["hard"])
    answer = t("The hardest task was {}: a mean score of {} over the {} runs that answered. {}", lang).format(
        f"<code>{esc(f['hard'])}</code>", n3(f["hard_mean"]), f["hard_n"],
        esc(t("({})", lang).format(t(what, lang))) if what else "")
    rows = [f'<tr>{agent_cell(x["key"], lang)}'
            + "".join(f'<td class="num">{n3(x["scores"].get(i))}</td>' for i in f["ids"]) + "</tr>"
            for x in f["table"]]
    head = [t("Contender", lang)] + [f"<code>{esc(i)}</code>" for i in f["ids"]]
    tasks = "".join(f"<li><code>{esc(i)}</code>: {esc(t(TASK_WHAT[i], lang))}</li>" for i in f["ids"]
                    if i in TASK_WHAT)
    body = (f"<p>{esc(t(FAILS_HOW, lang))}</p>"
            + (f'<ul class="plain">{tasks}</ul>' if tasks else "") + scroll(head, rows))
    foot = links([(f"#frames-{BOARD}", board_label(BOARD, lang))], [], {}, lang)
    bound = esc(t("Scores recomputed from each run's stored answer and its seed's truth; {} runs.", lang).format(
        f["runs"]))
    return section("fails", "Where does each model fail?", answer, body, foot, bound, lang)


CSS = P.CSS + """
section.finding { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
                  padding: .2rem 1rem 1rem; margin: 1.2rem 0 0; }
section.finding h2 { margin: .9rem 0 .5rem; }
section.finding p { max-width: 40rem; }
p.note { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: .5rem .8rem; }
details.fold { margin: .6rem 0; }
details.fold summary { cursor: pointer; font-weight: 600; }
p.answer { background: var(--bg); border-left: 4px solid var(--accent); border-radius: 6px; padding: .5rem .8rem; }
p.links, p.bound, p.sub { font-size: .88rem; color: var(--muted); }
section.finding .scroll { margin: .5rem 0; }
"""


def head_tags(data: dict, lang: str, image: str | None) -> str:
    url = URLS[lang]
    title, desc = t(TITLE, lang), t(DESC, lang)
    tags = [f'<link rel="canonical" href="{url}">']
    tags += [f'<link rel="alternate" hreflang="{P.TAGS[x]}" href="{URLS[x]}">' for x in P.LANGS]
    tags.append(f'<link rel="alternate" hreflang="x-default" href="{URLS["en"]}">')
    tags += [f'<meta property="og:type" content="article">', f'<meta property="og:title" content="{esc(title)}">',
             f'<meta property="og:description" content="{esc(desc)}">', f'<meta property="og:url" content="{url}">']
    if image:
        tags.append(f'<meta property="og:image" content="{P.PAGE_URL}{image}">')
    tags += ['<meta name="twitter:card" content="summary_large_image">',
             f'<meta name="twitter:title" content="{esc(title)}">',
             f'<meta name="twitter:description" content="{esc(desc)}">']
    if image:
        tags.append(f'<meta name="twitter:image" content="{P.PAGE_URL}{image}">')
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
          "inLanguage": P.TAGS[lang], "url": url, "mainEntityOfPage": url,
          "author": {"@type": "Person", "name": P.OWNER, "url": f"https://github.com/{P.OWNER}"},
          "isPartOf": {"@type": "WebSite", "name": "sports-video-coach", "url": P.PAGE_URL.rsplit("benchmark/", 1)[0]}}
    if data["date"]:
        ld["datePublished"] = ld["dateModified"] = data["date"]
    if image:
        ld["image"] = f"{P.PAGE_URL}{image}"
    # only plain text and URLs go in, so "</" cannot close the script element early
    text = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    tags.append(f'<script type="application/ld+json">{text}</script>')
    return "\n".join(tags)


def boards_note(fixed: dict | None, lang: str) -> str:
    """Near the top: the findings use the fresh-seed board; the fixed board differs, with the widest example."""
    if not fixed or not fixed["diff"]:
        return ""
    a, b = fixed["diff"]["fixed"], fixed["diff"]["fresh"]
    text = t(BOARDS_NOTE, lang).format(f'<a href="../#frames-{FIXED}">{esc(FIXED)}</a>', esc(name(b["key"], lang)),
                                   n3(a["above"]), n3(b["above"]))
    return f'<p class="note">{text}</p>'


def render(rows: list[dict], lang: str = "en", image: str | None = None, data: dict | None = None) -> str:
    """The findings page in `lang`; `image` is the og:image file name next to the leaderboard (or None)."""
    data = data if data is not None else findings_data(rows)
    ev = data["evidence"]
    parts = []
    if data["effort"]:
        parts.append(effort_section(data["effort"], ev, lang))
    if data["floor"]:
        parts.append(floor_section(data["floor"], lang))
    if data["code"]:
        parts.append(code_section(data["code"], lang))
    if data["local"]:
        parts.append(local_section(data["local"], ev, lang))
    if data["cost"]:
        parts.append(cost_section(data["cost"], lang, data.get("fixed")))
    if data["fails"]:
        parts.append(fails_section(data["fails"], lang))
    if not parts:
        parts.append(f'<div class="empty"><p>{esc(t("No runs yet, so no findings yet.", lang))}</p></div>')
    chips = f"<li>{esc(t('{} runs', lang).format(data['runs']))}</li>" + (
        f"<li>{esc(t('Latest result {}', lang).format(data['date']))}</li>" if data["date"] else "")
    home = "../../" if lang == "en" else "../../../"
    sw = ('<a class="switch" href="../zh/findings/" hreflang="zh-CN" lang="zh-CN">中文</a>' if lang == "en" else
          '<a class="switch" href="../../findings/" hreflang="en" lang="en">English</a>')
    rerun = t("Run any row again with one command: {}. Run an agent we have not tested and send the row: {}.",
              lang).format(f'<a href="../#rerun">{esc(t("the rerun section", lang))}</a>',
                           f'<a href="{P.WANTED_URL}">{esc(t("issue #7", lang))}</a>')
    nots = "".join(f"<li>{esc(t(x, lang))}</li>" for x in NOT_SHOWN)
    return f"""<!doctype html>
<html lang="{P.TAGS[lang]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t(TITLE, lang))}</title>
<meta name="description" content="{esc(t(DESC, lang))}">
{head_tags(data, lang, image)}
<style>{CSS}</style>
</head>
<body>
<main>
<p class="name"><a href="{home}">sports-video-coach</a> · <a href="../">{esc(t("Leaderboard", lang))}</a> {sw}</p>
<h1>{esc(t(TITLE, lang))}</h1>
<p class="lead">{esc(t(LEAD, lang))}</p>
<ul class="chips">{chips}</ul>
{boards_note(data.get("fixed"), lang)}
{"".join(parts)}
<h2 id="not-shown">{esc(t("What this benchmark does not show", lang))}</h2>
<ul class="plain">{nots}</ul>
<h2 id="rerun">{esc(t("Rerun it yourself", lang))}</h2>
<p>{rerun}</p>
<footer>{esc(t(BUILT, lang))} <a href="{P.REPO_URL}">sports-video-coach</a> (MIT).</footer>
</main>
</body>
</html>
"""


def image_for(card: bool, effort) -> str | None:
    """The og:image: the effort chart when it was drawn, else the share card, else none."""
    return effort_chart.NAMES["en"] if "en" in effort else share_card.NAME if card else None


def write(rows: list[dict], out_dir: Path, card: bool = False, effort=()) -> list[Path]:
    """Write findings/index.html and zh/findings/index.html under out_dir (the leaderboard's folder)."""
    data = findings_data(rows)
    image = image_for(card, effort)
    paths = []
    for lang, sub in (("en", Path("findings")), ("zh", Path("zh") / "findings")):
        d = out_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(render(rows, lang, image, data), encoding="utf8")
        paths.append(d / "index.html")
    return paths
