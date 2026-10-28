"""Local comparison page and source-aligned video for optional perception backends."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .perception_lab import read_json

NAMES = {"full": "RF-DETR 全图", "sahi": "SAHI 重叠切片", "wasb": "WASB 三帧", "kalicalib": "KaliCalib 球场"}
COLORS = {"full": (70, 215, 250), "sahi": (90, 245, 110), "wasb": (245, 180, 80)}


def overlay(frame, prediction, backend):
    import cv2
    import numpy as np
    canvas = frame.copy()
    if backend == "kalicalib":
        court = prediction["court"]
        if court.get("H"):
            H = np.array(court["H"])
            lines = [((0,0),(28,0)),((28,0),(28,15)),((28,15),(0,15)),((0,15),(0,0)),
                     ((14,0),(14,15)),((0,5.05),(5.8,5.05)),((5.8,5.05),(5.8,9.95)),
                     ((5.8,9.95),(0,9.95)),((28,5.05),(22.2,5.05)),
                     ((22.2,5.05),(22.2,9.95)),((22.2,9.95),(28,9.95))]
            for line in lines:
                points = cv2.perspectiveTransform(np.array([line], np.float32), H)[0]
                if np.isfinite(points).all() and abs(points).max() < 100000:
                    cv2.line(canvas, tuple(points[0].astype(int)), tuple(points[1].astype(int)), (80,200,250), 2)
        status = court["status"] + ": " + court["reason"]
    else:
        balls = sorted(prediction["ball"], key=lambda p: -p["score"])
        for n, ball in enumerate(balls):
            xy = tuple(round(v) for v in ball["xy"])
            cv2.circle(canvas, xy, 14 if n == 0 else 9, COLORS[backend], 3 if n == 0 else 1)
            cv2.putText(canvas, str(n+1), (xy[0]+15, xy[1]), cv2.FONT_HERSHEY_SIMPLEX, .55, COLORS[backend], 2)
        status = f'{len(balls)} candidates; thick circle = top score' if balls else 'NO OBSERVATION'
    return canvas, status


def render_video(samples_path, prediction_dir, output):
    import cv2
    import numpy as np
    from sports_video_coach import media
    samples = read_json(samples_path)
    fps = samples.get("playback_fps", 12)
    if not 0 < fps <= 240:
        raise ValueError("Invalid comparison playback fps")
    for a, b in zip(samples["samples"], samples["samples"][1:]):
        dt = b["t"] - a["t"]
        if a.get("clip") == b.get("clip") and 0 <= dt < 1 and abs(dt - 1/fps) > 1e-6:
            raise ValueError("Motion sampling does not match playback fps")
    root, prediction_dir = Path(samples_path).parent, Path(prediction_dir)
    backends = ["full", "sahi", "wasb", "kalicalib"]
    data = {b: {r["id"]:r for r in read_json(prediction_dir/f"{b}.json")["predictions"]} for b in backends}
    from .perception_backends import sha256
    for b in backends:
        if read_json(prediction_dir/f"{b}.json")["provenance"]["samples_sha256"] != sha256(samples_path):
            raise ValueError("Motion predictions do not match this manifest")
    kali_files = read_json(prediction_dir/"kalicalib.json")["provenance"]["model"]["files"]
    kali_variant = next((Path(p).stem for p in kali_files if p.endswith(".pth")), "unknown")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_name(output.stem + ".raw.mp4")
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 800))
    if not writer.isOpened():
        raise ValueError("Cannot create comparison video")
    try:
        for row in samples["samples"]:
            frame = cv2.imread(str(root / row["image"]))
            if frame is None:
                raise ValueError(f"Cannot read {row['image']}")
            panels = []
            for b in backends:
                annotated, status = overlay(frame, data[b][row["id"]], b)
                panel = np.zeros((400, 640, 3), np.uint8)
                h, w = annotated.shape[:2]
                scale = min(640/w, 360/h)
                sw, sh = round(w*scale), round(h*scale)
                ox, oy = (640-sw)//2, 40+(360-sh)//2
                panel[oy:oy+sh, ox:ox+sw] = cv2.resize(annotated, (sw, sh))
                title = b.upper() + (f" / {kali_variant}" if b == "kalicalib" else "")
                cv2.putText(panel, f'{title} | source {row["t"]:.2f}s', (12,17),
                            cv2.FONT_HERSHEY_SIMPLEX, .5, (240,240,240), 1)
                cv2.putText(panel, status, (12,34), cv2.FONT_HERSHEY_SIMPLEX, .37, (190,210,220), 1)
                panels.append(panel)
            writer.write(np.vstack([np.hstack(panels[:2]), np.hstack(panels[2:])]))
    finally:
        writer.release()
    # Use the shared media runner so ffmpeg failures propagate normally.
    with media.partial(output) as temporary:
        media.ffmpeg("-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
                     "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", str(temporary))
    raw.unlink()


def build_page(samples_path, prediction_dir, labels_path, court_labels_path=None):
    root = Path(prediction_dir)
    samples = read_json(samples_path)
    evaluation = read_json(root / "evaluation.json")
    from .perception_backends import sha256
    if evaluation["labels_sha256"] != sha256(labels_path):
        raise ValueError("Labels changed after evaluation; evaluate again before rendering")
    labels = {r["id"]: r for r in read_json(labels_path)["labels"]}
    data = {b: {r["id"]: r for r in read_json(root / f"{b}.json")["predictions"]} for b in NAMES}
    for b in NAMES:
        artifact = read_json(root / f"{b}.json")
        if artifact["provenance"]["samples_sha256"] != sha256(samples_path):
            raise ValueError("Predictions do not belong to this sample manifest")
        measured = evaluation["court"] if b == "kalicalib" else evaluation["ball"][b]
        if measured and measured["prediction_sha256"] != sha256(root/f"{b}.json"):
            raise ValueError("Predictions changed after evaluation")
    gallery = root / "frames"
    gallery.mkdir(exist_ok=True)
    for row in samples["samples"]:
        expected = read_json(root / "full.json")["provenance"]["image_sha256"][row["id"]]
        if sha256(Path(samples_path).parent / row["image"]) != expected:
            raise ValueError("Source frame changed after inference")
        shutil.copyfile(Path(samples_path).parent / row["image"], gallery / row["image"])
    def percentage(value):
        return "—" if value is None else f"{value*100:.1f}%"
    table = []
    for b in ("full", "sahi", "wasb"):
        measured = evaluation["ball"][b]
        m = measured["metrics"]
        table.append(f'<tr><th>{NAMES[b]}</th><td>{m["tp"]}/{m["visible"]}</td>'
                     f'<td>{percentage(m["precision"])}</td><td>{percentage(m["recall"])}</td>'
                     f'<td>{m["fp"]}</td><td>{m["extra_candidates"]}</td>'
                     f'<td>{measured["runtime"]["median_seconds"]*1000:.0f} ms</td></tr>')
    court = [r["court"] for r in data["kalicalib"].values()]
    accepted = sum(r["H"] is not None for r in court)
    manual_court = read_json(court_labels_path) if court_labels_path else None
    payload = {"samples": samples["samples"], "predictions": data, "labels": labels,
               "courtLabels": manual_court, "names": NAMES}
    serialized = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>篮球录像 · 视觉模型实测</title>
<style>
:root{color-scheme:dark;font-family:system-ui,"Microsoft YaHei",sans-serif;background:#0b1320;color:#e9f0f7}
*{box-sizing:border-box}body{margin:0}main{max-width:1120px;margin:auto;padding:32px 20px 60px}a{color:#74d8ff}
h1{font-size:clamp(27px,5vw,42px);line-height:1.2}h2{font-size:23px;margin:0 0 16px}p{max-width:75ch;line-height:1.7}
.kicker{color:#74d8ff;letter-spacing:.12em;font-size:13px}.card{background:#142132;border:1px solid #29415b;border-radius:18px;padding:24px;margin:24px 0}
.tag{display:inline-block;background:#22364c;border-radius:20px;padding:6px 12px;margin:3px;font-size:13px}.warn{color:#ffd998}
.scroll{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}th,td{text-align:left;padding:13px;border-bottom:1px solid #304358;font-size:14px}
video,canvas{width:100%;display:block;background:#05090e;border-radius:10px}select,button{font:inherit;background:#22364c;color:inherit;border:1px solid #55718c;border-radius:8px;padding:9px;max-width:100%}
.controls{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:15px}label{display:flex;align-items:center;gap:6px}summary{cursor:pointer;line-height:1.7}.muted{color:#a9b9cb;font-size:14px}
@media(max-width:500px){main{padding:22px 12px}.card{padding:16px}th,td{padding:10px}}
</style><main><div class="kicker">PERCEPTION LAB / 录像验证</div>
<h1>哪些模型真的补上了？</h1>
<p>同一场比赛、同一组原始帧，比较全图检测、切片检测、三帧球定位和球场映射。下方保留成功与失败结果，方便逐帧核验。</p>
<div><span class="tag">45 个标注样本</span><span class="tag">人工标注先于模型对照</span><span class="tag">本地运行</span><span class="tag">实验结果，不改官方数据</span></div>
<section class="card"><h2>球定位：命中与误检同时看</h2><div class="scroll"><table><thead><tr><th>方法</th><th>命中/可见</th><th>精确率</th><th>召回率</th><th>误检帧</th><th>额外候选</th><th>中位推理耗时</th></tr></thead><tbody>TABLE</tbody></table></div>
<p class="muted">每帧取最高分的一个球候选；距人工球心 ≤12 px 算命中。定位错误同时计一次误检和一次漏检。看不清的帧排除；额外候选单列，不用“检出数量”代替准确率。</p>
<p class="warn">这只是单场小样本诊断。WASB 的 heatmap mass 与检测器置信度不能横向比较；切片检测也可能找到邻场球或背景误检。</p></section>
VIDEO_SECTION
<section class="card"><h2>逐帧检查</h2><div class="controls"><button id="prev">上一帧</button><select id="sample" aria-label="验证帧"></select><button id="next">下一帧</button></div>
<div class="controls"><label><input type="checkbox" id="full" checked>全图（青）</label><label><input type="checkbox" id="sahi" checked>SAHI（绿）</label><label><input type="checkbox" id="wasb" checked>WASB（橙）</label><label><input type="checkbox" id="truth" checked>人工球心（粉）</label><label><input type="checkbox" id="court" checked>人工球场点</label></div>
<canvas id="frame" width="1280" height="720"></canvas><p id="detail"></p><p class="muted">圆上的数字表示该方法内部的分数排序；细圈为额外候选。球场点仅用于独立核验，不用于拟合这些模型。</p></section>
<section class="card"><h2>KaliCalib 球场映射</h2><p>主实验（KALI_WEIGHT）：45 帧中通过几何门槛的候选：COURT / 45。所有候选仍需独立核验；没有自动替换现有球场标定。</p>
<p>COURT_LABELS 若模型候选被拒绝，就不计算一个看起来很好的重投影误差，也不回退到默认“平均球场”。</p></section>
<details class="card"><summary>方法、边界与可复现文件</summary><p>RF-DETR 与 SAHI 共用同一权重、DETECT_THRESHOLD 检测阈值；SAHI 使用 SLICE_SIZE px 切片、20% 重叠、全图预测和 IOU 0.5 NMS。WASB 使用官方篮球权重、0.5 热图阈值和原视频上间隔 TEMPORAL_STEP 帧的三帧输入。</p>
<p>推理耗时排除预热、模型加载和视频解码；GPU 共享环境下测量，不是端到端速度承诺。人工球心与线交点有像素误差，FIBA 场地尺寸未现场测量。模型未针对这组标签调参。</p>
<p><a href="evaluation.json">评估 JSON（含 8/20 px 敏感性）</a> · <a href="full.json">全图原始结果</a> · <a href="sahi.json">SAHI 原始结果</a> · <a href="wasb.json">WASB 原始结果</a> · <a href="kalicalib.json">KaliCalib 原始结果</a></p></details>
REPORT_LINK</main>
<script type="application/json" id="data">PAYLOAD</script><script>
const d=JSON.parse(document.getElementById('data').textContent), sel=document.getElementById('sample'), canvas=document.getElementById('frame'),ctx=canvas.getContext('2d');
d.samples.forEach((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1} / ${d.samples.length} · ${r.t.toFixed(2)} 秒`;sel.append(o)});
let generation=0;
function circle(xy,color,r,text){ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;ctx.beginPath();ctx.arc(xy[0],xy[1],r,0,Math.PI*2);ctx.stroke();ctx.font='18px sans-serif';if(text)ctx.fillText(text,xy[0]+r+3,xy[1])}
function draw(){const token=++generation,r=d.samples[Number(sel.value)],im=new Image();im.onload=()=>{if(token!==generation)return;canvas.width=r.width;canvas.height=r.height;ctx.drawImage(im,0,0);for(const [b,col] of Object.entries({full:'#46d7fa',sahi:'#5af56e',wasb:'#f5b450'})){if(!document.getElementById(b).checked)continue;[...d.predictions[b][r.id].ball].sort((a,b)=>b.score-a.score).forEach((p,i)=>circle(p.xy,col,i===0?15:8,String(i+1)))}const label=d.labels[r.id];if(document.getElementById('truth').checked&&label.xy)circle(label.xy,'#ff6dd9',5,'GT');if(document.getElementById('court').checked&&d.courtLabels){const c=d.courtLabels.labels.find(x=>x.id===r.id);if(c)c.points.forEach(p=>circle(p.image_xy,'#ffffff',5,p.name))}document.getElementById('detail').textContent=`${r.t.toFixed(2)} 秒 · 人工判断：${({visible:'球可见',occluded:'球被遮挡',unclear:'看不清，排除评分'})[label.state]} · ${label.note||''}`};im.src='frames/'+r.image}
sel.onchange=draw;document.querySelectorAll('input').forEach(x=>x.onchange=draw);document.getElementById('prev').onclick=()=>{sel.value=Math.max(0,Number(sel.value)-1);draw()};document.getElementById('next').onclick=()=>{sel.value=Math.min(d.samples.length-1,Number(sel.value)+1);draw()};draw();
</script></html>'''
    challenge = ""
    challenge_path = root / "challenge" / "evaluation.json"
    if challenge_path.exists():
        c = read_json(challenge_path)
        c_predictions = read_json(root / "challenge" / "kalicalib.json")["predictions"]
        n = sum(p["court"].get("H") is not None for p in c_predictions)
        error = c.get("median_error_px")
        error_text = "无可用候选" if error is None else f'{error:.1f} px'
        challenge = (f'<p>另测官方 challenge 权重：{n}/{len(c_predictions)} 帧形成几何候选。'
                     f'独立交点核验覆盖 {c["points_evaluated"]} 点，中位误差 {error_text}。'
                     '这是探索性比较，候选仍未获准自动写入球场标定。</p>')
    count = len(samples["samples"])
    from sports_video_coach import media
    video_section = ""
    if (root/"comparison.mp4").exists():
        duration = media.duration_s(root/"comparison.mp4")
        video_section = (f'<section class="card"><h2>{duration:.0f} 秒四路对照视频</h2>'
            '<video controls playsinline preload="metadata" src="comparison.mp4"></video>'
            '<p class="muted">按原时间播放，无音轨；切换片段时原视频时间跳转。'
            '圈来自当前帧的输出，粗圈为最高分，没有输出显示 NO OBSERVATION。'
            'KaliCalib 权重名称见视频左上标签；所有球场线仍是未确认候选。</p></section>')
    court_note = (f'{len(manual_court["labels"])} 帧共 {sum(len(r["points"]) for r in manual_court["labels"])} 个人工球场交点已独立标注。'
                  if manual_court else "尚未提供独立球场交点标注。")
    primary = read_json(root/"kalicalib.json")["provenance"]["model"]["files"]
    kali_weight = next((Path(p).stem for p in primary if p.endswith(".pth")), "unknown")
    parameters = read_json(root/"sahi.json")["provenance"]
    document = (document.replace("COURT_LABELS", court_note).replace("KALI_WEIGHT", html.escape(kali_weight))
                .replace("DETECT_THRESHOLD", str(parameters["model"]["threshold"]))
                .replace("SLICE_SIZE", str(parameters["slice_size"]))
                .replace("TEMPORAL_STEP", str(read_json(root/"wasb.json")["provenance"]["temporal_step"]))
                .replace("VIDEO_SECTION", video_section)
                .replace("REPORT_LINK", '<p><a href="../index.html">返回完整比赛报告</a></p>' if (root.parent/"index.html").exists() else ""))
    document = document.replace("TABLE", "".join(table)).replace("COURT", str(accepted)).replace("PAYLOAD", serialized)
    document = document.replace("45 个标注样本", f"{count} 个标注样本").replace("45 帧中", f"{count} 帧中").replace(" / 45", f" / {count}")
    document = document.replace("<h2>KaliCalib 球场映射</h2>", "<h2>KaliCalib 球场映射</h2>" + challenge)
    (root / "index.html").write_text(document, encoding="utf8")
    return root / "index.html"


def report_section(folder, lang, first):
    """Link the diagnostic artifacts into the team report, only when they exist."""
    folder = Path(folder)
    if not (folder / "game.json").exists() or not (folder / "perception-lab/index.html").exists():
        return "", []
    title = "视觉模型对照实验" if lang == "zh" else "Perception backend comparison"
    text = ("查看 WASB、SAHI、KaliCalib 的逐帧对照、人工标注评分与验证视频。实验候选不计入比赛统计。"
            if lang == "zh" else "Compare WASB, SAHI and KaliCalib against independent labels and watch the validation video. Experimental candidates do not change game statistics.")
    label = "打开对照页" if lang == "zh" else "Open comparison"
    return (f'<h2 id="{lang}-s{first}">{title}</h2><p>{text}</p>'
            f'<p><a href="perception-lab/index.html">{label}</a></p>'), [title]
