"""`sports-video-coach demo`: see every deliverable in about a minute, no agent and no video of your own.

Draws a synthetic video (a red block running a shuttle between two cones, no people), starts a generic analysis
unit from it, copies in a pre-written film review, report, narration and film script (`files/`), and runs the
normal pipeline: frames, clips, narration, page, a scripted QA self-check, explained video. With your own video
the agent writes those files; here they come with the package so the run needs nothing but ffmpeg (and the
network for edge-tts, unless --offline).

usage: sports-video-coach demo [--out <folder>] [--lang en zh] [--no-film] [--offline]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

from .. import media, pipeline as P, workspace
from ..plugins.generic import new, unit as U

FILES = Path(__file__).parent / "files"
SECONDS = 22
# The block's x position (px) over time: four 4 s legs between the cones, turns of 1.5 s, 0.5 s and 1.5 s.
# The pre-written review and report describe exactly this; change both together.
PATH_X = ("if(lt(t,4),60+120*t,if(lt(t,5.5),540,if(lt(t,9.5),540-120*(t-5.5),if(lt(t,10),60,"
          "if(lt(t,14),60+120*(t-10),if(lt(t,15.5),540,if(lt(t,19.5),540-120*(t-15.5),60)))))))")


def draw_video(out: Path) -> Path:
    """Write the synthetic drill video: green floor, a white line, two orange cones, the red block."""
    floor = ("drawbox=x=0:y=260:w=640:h=4:c=white:t=fill,"
             "drawbox=x=40:y=232:w=20:h=28:c=0xff8c1a:t=fill,drawbox=x=580:y=232:w=20:h=28:c=0xff8c1a:t=fill")
    media.ffmpeg("-f", "lavfi", "-i", f"color=c=0x2f6b3a:s=640x360:r=25:d={SECONDS}",
                 "-f", "lavfi", "-i", f"color=c=0xd0312d:s=30x60:r=25:d={SECONDS}",
                 "-filter_complex", f"[0]{floor}[bg];[bg][1]overlay=x='{PATH_X}':y=200[v]",
                 "-map", "[v]", "-pix_fmt", "yuv420p", "-c:v", "libx264", out)
    return out


def copy_files(folder: Path, langs: list[str]) -> None:
    """The pre-written agent outputs, for the chosen languages; files already there are kept."""
    want = {"review.json": folder / "run" / "review" / "review.json"}
    for lang in langs:
        want[P.readme(lang)] = folder / P.readme(lang)
        want[f"listen.{lang}.md"] = folder / f"listen.{lang}.md"
        want[f"film.{lang}.md"] = folder / f"film.{lang}.md"
    for name, dst in want.items():
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FILES / name, dst)


def self_check(g: U.Analysis) -> list[str]:
    """What the page is missing: it must link every clip and audio file the run made. Not a browser check."""
    page = g.folder / "index.html"
    if not page.exists():
        return [f"{page} missing"]
    html = page.read_text(encoding="utf8")
    media_files = [*sorted(g.folder.glob("clips/*.mp4")), *sorted(g.folder.glob("listen.*.mp3"))]
    errs = [f"index.html does not link {p.relative_to(g.folder).as_posix()}" for p in media_files
            if p.relative_to(g.folder).as_posix() not in html]
    if not list(g.folder.glob("clips/*.mp4")):
        errs.append("no clips were cut")
    return errs


def write_qa(g: U.Analysis) -> None:
    errs = self_check(g)
    if errs:
        sys.exit("[demo] page self-check failed:\n  " + "\n  ".join(errs))
    text = ("PASS\n\nScripted self-check by `sports-video-coach demo`, not a browser check: index.html links every "
            "clip and audio file. With your own video the agent checks the page in a browser instead.\n\n"
            f"checked: {P.qa_hash(g)}\n")
    media.write_text_atomic(g.folder / "qa.md", text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach demo", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", help="the demo folder (default: <workspace>/analysis/demo/<today>)")
    ap.add_argument("--lang", nargs="+", choices=["en", "zh"], default=["en"], help="languages (default: en)")
    ap.add_argument("--no-film", action="store_true", help="stop after the page (skips the explained video)")
    ap.add_argument("--offline", action="store_true",
                    help="no network: clips and the page only (narration and the film need online text-to-speech)")
    a = ap.parse_args(argv)
    if not (shutil.which(media.ffmpeg_exe()) and shutil.which("ffprobe")):
        sys.exit("[demo] needs ffmpeg and ffprobe on PATH (https://ffmpeg.org/download.html)")
    t0 = time.monotonic()
    folder = Path(a.out) if a.out else workspace.root() / "analysis" / "demo" / time.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / "drill.mp4"
    if not video.exists():
        draw_video(video)
    new.main([str(video), "--sport", "shuttle run (synthetic demo)", "--focus", "the red block",
              "--name", "demo", "--lang", *a.lang, "--every", "2", "--out", str(folder)])
    arts = ["clips", "html"] if a.offline else ["clips", "narration", "html"] + ([] if a.no_film else ["film"])
    gj = folder / "analysis.json"
    data = json.loads(gj.read_text(encoding="utf8"))
    if data.get("artifacts") != arts:
        media.write_text_atomic(gj, json.dumps({**data, "artifacts": arts}, ensure_ascii=False, indent=1) + "\n")
    copy_files(folder, a.lang)
    code = P.drive(U.Analysis.load(folder), U.STEPS, until="html")
    if code == 0:
        g = U.Analysis.load(folder)
        if not P.qa_done(g):
            write_qa(g)
            print("[demo] qa: wrote qa.md (scripted self-check, stands in for the agent's browser check)")
        code = P.drive(g, U.STEPS)
    if code != 0:
        print(f"[demo] stopped with exit {code}; the lines above say why. Run the same command again to resume.")
        return code
    print(f"\n[demo] done in {time.monotonic() - t0:.0f} s. Open {folder / 'index.html'} in a browser.")
    for lang in a.lang:
        if (folder / f"film.{lang}.mp4").exists():
            print(f"[demo] explained video: {folder / f'film.{lang}.mp4'}")
    print("[demo] The video is drawn and the review is pre-written. With your own video, your agent writes them:\n"
          "       sports-video-coach run my_video.mp4 --sport tennis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
