"""Reviewable basketball perception evidence in the existing report page."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .perception import SCHEMA, evidence_path

LABELS = {
    "zh": dict(title="逐帧识别 · 录像验证", note="自动识别提供复查线索，未确认的结果不计入比赛统计。",
               shot="投篮", rebound="篮板", turnover="球权变化", steal="抢断", pass_="传球", dribble="运球",
               pending="待复查", confirmed="已复查", rejected="识别错误", unclear="看不清",
               made="可能命中", missed="可能未进", unknown="结果看不清", us="我方", them="对手",
               model="模型判断", review="复查记录", detail="查看证据与识别覆盖",
               coverage="分析覆盖", seconds="秒", ball="检出球的帧", poses="姿态观测", numbers="号码观测",
               identities="身份候选", video="观看带标注的验证视频", more="其余事件仍保留在本地证据文件中。",
               candidates="自动识别候选", coverage_note="检出位置仍可能有误，预测补点不算检出。姿态和号码会跨帧重复观测，不代表独立核验次数。",
               offensive="可能是进攻篮板", defensive="可能是防守篮板", steal_cause="可能由抢断造成",
               validation="独立片段复查", validation_note="只代表表内抽查片段，不代表全场准确率。调试片段曾用于选择识别设置；进球结果和球队只在配对成功的出手中比较。",
               window="录像时间", split="用途", development="调试", validation_split="验证", diagnostic="诊断",
               attempts="找到 / 录像出手", extra="多报", outcomes="结果正确 / 可判", teams="球队正确 / 可判",
               external="部分外部数据未验证处理完成状态或画面坐标；只提供事件线索，不画位置或计入独立评估。",
               truncated="片段已截短，未显示整个动作。"),
    "en": dict(title="Frame analysis · Film validation", note="Automatic candidates guide review; unconfirmed results do not enter game statistics.",
               shot="Shot", rebound="Rebound", turnover="Possession change", steal="Steal", pass_="Pass", dribble="Dribble",
               pending="Pending review", confirmed="Reviewed", rejected="Incorrect detection", unclear="Unclear",
               made="Possible make", missed="Possible miss", unknown="Outcome unclear", us="Us", them="Opponent",
               model="Model candidate", review="Review notes", detail="Evidence and coverage",
               coverage="Analyzed", seconds="seconds", ball="Frames with observed ball", poses="Pose observations",
               numbers="Number observations", identities="Identity candidates", video="Watch the annotated validation video",
               more="Additional events remain in the local evidence file.",
               candidates="Automatic event candidates", coverage_note="Detected positions may be wrong; predicted ball positions are excluded. Pose and number observations repeat across frames and are not independent confirmations.",
               offensive="Possible offensive rebound", defensive="Possible defensive rebound", steal_cause="Possible steal",
               validation="Independent clip review", validation_note="These sampled windows do not establish full-game accuracy. Development footage helped choose settings; outcome and team checks cover matched attempts only.",
               window="Video time", split="Use", development="Development", validation_split="Validation", diagnostic="Diagnostic",
               attempts="Found / labelled", extra="Extra", outcomes="Outcome correct / known", teams="Team correct / known",
               external="Some external data has unverified completion or frame coordinates. It supplies event candidates only, without position overlays or independent evaluation.",
               truncated="Shortened clip; the full action is not shown."),
}


def clock(t):
    return f"{int(t) // 60:02d}:{t % 60:04.1f}"


def evaluation_table(doc: dict, ui: dict) -> str:
    evaluation = doc.get("evaluation")
    if not evaluation:
        return ""
    esc = html.escape
    ratio = lambda a, b: f"{a} / {b}" if b else "–"
    rows = []
    for w in evaluation["windows"]:
        purpose = ui.get("validation_split" if w["split"] == "validation" else w["split"], w["split"])
        cells = [f'{clock(w["start"])}–{clock(w["end"])}', purpose,
                 ratio(w["matched"], w["labelled_shots"]), w["unmatched_candidates"],
                 ratio(w["outcome_correct"], w["outcome_labels"]), ratio(w["team_correct"], w["team_labels"])]
        rows.append("<tr>" + "".join(f"<td>{esc(str(c))}</td>" for c in cells) + "</tr>")
    head = "".join(f'<th scope="col">{esc(ui[k])}</th>' for k in ("window", "split", "attempts", "extra", "outcomes", "teams"))
    return (f'<h3>{esc(ui["validation"])}</h3><p>{esc(ui["validation_note"])}</p>'
            f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def sections(folder: Path, lang: str, first: int, embed: bool = False) -> tuple[str, list[str]]:
    # Unresolved global IDs cannot be attributed to a focus player's personal page.
    if not (folder / "game.json").exists():
        return "", []
    path = evidence_path(folder)
    if path is None or not path.exists():
        return "", []
    doc = json.loads(path.read_text(encoding="utf8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unsupported perception evidence schema")
    ui = LABELS.get(lang, LABELS["en"])
    esc = html.escape
    counts = doc["counts"]
    files = folder / "perception"
    manifest = json.loads((files / "media.json").read_text(encoding="utf8")) if (files / "media.json").exists() else {}
    shown = set(manifest.get("event_ids", []))
    truncated = {w["id"] for w in manifest.get("windows", []) if w.get("truncated")}
    events = [e for e in doc["events"] if e["id"] in shown]
    cards = []
    for event in events:
        eid = event["id"]
        clip = files / f"{eid}.mp4"
        kind = ui.get("pass_" if event["type"] == "pass" else event["type"], event["type"])
        status = ui[event["review_status"]]
        team = ui.get(event.get("team"), "?")
        result = ui.get(event.get("result"), ui["unknown"]) if event["type"] == "shot" else ""
        if event["type"] == "rebound":
            result = ui.get(event.get("rebound_type"), "")
        elif event["type"] == "turnover" and event.get("cause") == "steal":
            result = ui["steal_cause"]
        review = event.get("review") or {}
        note = review.get("note_zh" if lang == "zh" else "note", review.get("note", ""))
        video = f'<video controls preload="none" playsinline src="perception/{esc(eid)}.mp4"></video>' if clip.exists() and not embed else ""
        cards.append(f'<article class="perception-card"><h3>{esc(kind)} · {clock(event["start"])}</h3>'
                     f'<p><b>{esc(status)}</b></p>{video}<p>{esc(ui["model"])}: {esc(team)} {esc(result)}</p>'
                     + (f'<p>{esc(ui["review"])}: {esc(note)}</p>' if note else "")
                     + (f'<p>{esc(ui["truncated"])}</p>' if eid in truncated else "") + '</article>')
    metric = lambda label, value: f'<div><dt>{esc(label)}</dt><dd>{esc(str(value))}</dd></div>'
    totals = "".join(metric(ui.get("pass_" if k == "pass" else k, k), v) for k, v in doc["event_counts"].items())
    health = "".join(metric(ui[k], v) for k, v in (
        ("coverage", f'{doc["analyzed_seconds"]:.0f} / {doc.get("video_duration", doc["analyzed_seconds"]):.0f} {ui["seconds"]}'),
        ("ball", f'{counts.get("ball_observed_frames", 0)} / {counts["frames"]}'),
        ("poses", counts.get("pose_observations", 0)), ("numbers", counts.get("number_observations", 0)),
        ("identities", len(doc["identities"]))))
    reel = ('<video controls preload="none" playsinline src="perception/validation.mp4"></video>'
            if events and (files / 'validation.mp4').exists() and not embed else '')
    external = (f'<p>{esc(ui["external"])}</p>' if any(
        s.get("finalization") == "external_unverified" for s in doc["sources"]) else "")
    content = (f'<h2 id="{lang}-s{first}">{esc(ui["title"])}</h2><div id="{lang}-perception" class="perception-panel">'
               f'<p>{esc(ui["note"])}</p><h3>{esc(ui["candidates"])}</h3><dl class="perception-metrics">{totals}</dl>'
               f'<details><summary>{esc(ui["detail"])}</summary><dl class="perception-metrics">{health}</dl>'
               f'<p>{esc(ui["coverage_note"])}</p>{external}</details>'
               + evaluation_table(doc, ui)
               + (f'<h3>{esc(ui["video"])}</h3>{reel}' if reel else '')
               + f'<div class="perception-grid">{"".join(cards)}</div><p>{esc(ui["more"])}</p></div>')
    style = '<style>.perception-panel video{width:100%;max-height:540px;background:#101820;border-radius:10px}.perception-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:20px;margin-top:20px}.perception-card{padding:16px;border:1px solid var(--line,#ccc);border-radius:12px}.perception-panel p{line-height:1.6;max-width:75ch}.perception-metrics{display:flex;flex-wrap:wrap;gap:14px 24px}.perception-metrics dt{font-size:.85em;color:var(--muted)}.perception-metrics dd{margin:4px 0;font-weight:700}.perception-panel details{margin:18px 0}.perception-panel table{font-size:.85em}.perception-panel th,.perception-panel td{white-space:nowrap}</style>'
    return style + content, [ui["title"]]
