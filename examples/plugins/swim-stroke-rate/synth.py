"""Stage `synth <out.mp4> [--spm 45] [--seconds 8]`: a drawn swimmer seen from the side, arm turning at a known rate.

The truth for tests and for trying the plugin without real video: a body, a head and one arm that makes one full
revolution per stroke cycle, on a water background with a little noise. No video is committed; make one when needed.
"""
import argparse
import math
from pathlib import Path

import cv2
import numpy as np


def write(out: Path, spm: float = 45.0, seconds: float = 8.0, fps: int = 30, size=(320, 180), seed: int = 0) -> Path:
    w, h = size
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(seed)
    shoulder, arm = (w // 2 + 30, h // 2), h // 3
    for i in range(int(seconds * fps)):
        t = i / fps
        img = np.full((h, w, 3), (160, 110, 40), np.uint8)                          # water (BGR)
        img = cv2.add(img, rng.integers(0, 12, img.shape, dtype=np.uint8))
        cv2.ellipse(img, (w // 2, h // 2), (70, 14), 0, 0, 360, (90, 140, 210), -1)  # body
        cv2.circle(img, (w // 2 + 80, h // 2 - 4), 12, (60, 90, 170), -1)          # head
        a = 2 * math.pi * spm / 60 * t                                               # one turn per cycle
        hand = (int(shoulder[0] + arm * math.cos(a)), int(shoulder[1] - arm * math.sin(a)))
        cv2.line(img, shoulder, hand, (90, 140, 210), 9)                            # arm
        kick = int(6 * math.sin(2 * math.pi * 3 * spm / 60 * t))                    # six-beat kick, faster
        cv2.line(img, (w // 2 - 70, h // 2), (w // 2 - 110, h // 2 + kick), (90, 140, 210), 7)
        vw.write(img)
    vw.release()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach swim-stroke-rate:synth")
    ap.add_argument("out")
    ap.add_argument("--spm", type=float, default=45.0, help="true stroke rate, cycles per minute")
    ap.add_argument("--seconds", type=float, default=8.0)
    a = ap.parse_args(argv)
    print(f"wrote {write(Path(a.out), a.spm, a.seconds).as_posix()} ({a.spm} cycles/min, {a.seconds} s)")


if __name__ == "__main__":
    main()
