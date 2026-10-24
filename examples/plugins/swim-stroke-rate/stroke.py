"""Stage `stroke <video> --out <folder>`: stroke rate (stroke cycles per minute) -> <folder>/stroke.json.

Side view, camera roughly still. Each frame is shrunk to grey 64x36; the frames' first few principal components
over time carry the main periodic motions, and the peak of their summed spectrum in 15-120 cycles/min is the stroke
rate (a turning arm needs two components, a sine and a cosine). One cycle = one full arm revolution.
Plain OpenCV and NumPy: no GPU, no model download.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

LO_HZ, HI_HZ = 0.25, 2.0      # 15..120 cycles per minute
COMPONENTS = 4


def signal(video: str) -> tuple[float, np.ndarray]:
    """(fps, frames x COMPONENTS): the frames projected on their first principal components."""
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    rows = []
    ok, img = cap.read()
    while ok:
        g = cv2.cvtColor(cv2.resize(img, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        rows.append(g.astype(np.float32).ravel())
        ok, img = cap.read()
    cap.release()
    if len(rows) < 2:
        raise SystemExit(f"{video}: no frames read")
    x = np.array(rows)
    x -= x.mean(axis=0)
    _, _, vt = np.linalg.svd(x, full_matrices=False)
    return fps, x @ vt[:COMPONENTS].T


def rate(sig: np.ndarray, fps: float) -> tuple[float, float]:
    """(peak Hz in [LO_HZ, HI_HZ], peak strength) of `sig` (frames x components): summed zero-padded spectra,
    parabolic refinement of the top bin. Strength = peak / mean of the band; under about 3 the rhythm is weak
    (few cycles, or another motion): check the per-window rates."""
    s = (sig - sig.mean(axis=0)) * np.hanning(len(sig))[:, None]
    n = 1 << (len(s) * 8 - 1).bit_length()
    spec = np.abs(np.fft.rfft(s, n, axis=0)).sum(axis=1)
    f = np.fft.rfftfreq(n, 1 / fps)
    band = np.where((f >= LO_HZ) & (f <= HI_HZ))[0]
    k = band[np.argmax(spec[band])]
    for m in (3, 2):  # a kick (2 or 3 per arm cycle) can out-peak the arms: prefer a strong peak at 1/m of it
        j = int(round(k / m))
        if f[j] >= LO_HZ:
            j = j - 2 + int(np.argmax(spec[j - 2:j + 3]))
            if spec[j] >= 0.5 * spec[k]:
                k = j
                break
    a, b, c = spec[k - 1], spec[k], spec[k + 1]
    d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else 0.0
    return float((k + d) * fps / n), float(spec[k] / (spec[band].mean() + 1e-9))


def measure(video: str, window_s: float = 10.0) -> dict:
    """The whole video's rate, and the rate per window (half-overlapping) to show a change over time."""
    fps, sig = signal(video)
    hz, strength = rate(sig, fps)
    win = int(window_s * fps)
    windows = []
    for i in range(0, max(1, len(sig) - win + 1), max(1, win // 2)):
        h, s = rate(sig[i:i + win], fps)
        windows.append({"start_s": round(i / fps, 2), "end_s": round(min(i + win, len(sig)) / fps, 2),
                        "spm": round(h * 60, 1), "peak_strength": round(s, 1)})
    return {"stroke_rate_spm": round(hz * 60, 1), "cycle_s": round(1 / hz, 3), "peak_strength": round(strength, 1),
            "duration_s": round(len(sig) / fps, 2), "fps": fps, "frames": len(sig),
            "method": "PCA of 64x36 grey frames, spectral peak in 15-120 cycles/min",
            "unit": "stroke cycles per minute (one full arm revolution = one cycle)", "windows": windows}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach swim-stroke-rate:stroke")
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--window", type=float, default=10.0, help="seconds per window for the rate over time")
    a = ap.parse_args(argv)
    res = measure(a.video, a.window)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stroke.json").write_text(json.dumps(res, indent=1), encoding="utf8")
    print(f"stroke rate {res['stroke_rate_spm']} /min (cycle {res['cycle_s']} s, peak strength "
          f"{res['peak_strength']}) -> {(out / 'stroke.json').as_posix()}")


if __name__ == "__main__":
    main()
