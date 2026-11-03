"""Stage `new <video...> [options]`: start a fitness session folder, as the generic `new` does (same options), with
"plugin": "fitness" in its analysis.json. Several videos are joined into video.mp4; the pose pass still reads each
source video at its own frame rate (analysis.json `sources`)."""
from __future__ import annotations

import json
import sys

from sports_video_coach import media
from sports_video_coach.plugins.generic import new as G

from . import NAME, SPORT


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--sport" not in argv:
        argv += ["--sport", SPORT]
    if "--sport-zh" not in argv and not any(a.startswith("zh=") for a in argv):
        argv += ["--sport-zh", "体能训练"]
    folder = G.main(argv)
    p = folder / "analysis.json"
    data = json.loads(p.read_text(encoding="utf8"))
    data.update(plugin=NAME, kind="analysis")
    media.write_text_atomic(p, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"[new] fitness session: {folder.as_posix()}")
    return folder


if __name__ == "__main__":
    main()
