"""Contact-sheet labels: every tile reads the video time of the frame it shows, on main and zoom sheets alike."""
import shutil

import pytest

from sports_video_coach import frames, media
from sports_video_coach.timefmt import seconds

FPS, STEP = 25, 8  # frame k is grey level (k % 32) * STEP, so a tile tells which frame it shows


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("needs ffmpeg")
    out = tmp_path_factory.mktemp("v") / "count.mp4"
    media.ffmpeg("-f", "lavfi", "-i", f"color=c=black:s=160x120:r={FPS}:d=6,format=gray,geq=lum='mod(N,32)*{STEP}'",
                 "-pix_fmt", "yuv420p", out)
    return out


def shown(sheet, n: int, cols: int, width: int) -> int:
    """Frame number (mod 32) of tile `n` of a sheet, from its grey level away from the label."""
    import cv2
    img = cv2.imread(str(sheet), cv2.IMREAD_GRAYSCALE)
    th = round(120 * width / 160)
    r, c = divmod(n, cols)
    cell = img[r * th + th // 2:(r + 1) * th, c * width + width // 2:(c + 1) * width]
    return round(cell.mean() / STEP) % 32


@pytest.mark.parametrize("args", [dict(every=1), dict(every=2), dict(every=0.5),
                                  dict(every=0.2, start=1.0, end=2.4), dict(every=1, start=2.3, end=5)])
def test_every_label_is_the_time_of_the_frame_shown(tmp_path, video, args):
    cols, width = 4, 160
    data = frames.build(video, tmp_path / "f", cols=cols, rows=3, width=width, **args)
    for s in data["sheets"]:
        for n, label in enumerate(s["tiles"]):
            k = shown(tmp_path / "f" / s["file"], n, cols, width)  # 00:02 must show ~2.0 s, not 2.5 s
            frames_at = [f for f in range(6 * FPS) if f % 32 == k and abs(f / FPS - seconds(label)) <= 0.05]
            assert frames_at, f"{s['file']} tile {n} labelled {label} shows frame {k} (mod 32)"


def test_whole_second_sheets_sample_whole_seconds_and_say_so():
    assert frames.times(6, 1) == [1, 2, 3, 4, 5] and frames.times(6, 2) == [1, 3, 5] and frames.times(9, 3) == [2, 5, 8]
    assert frames.labels(frames.times(6, 2)) == 0
    assert frames.times(3, 1.5) == [0.8, 2.3] and frames.labels(frames.times(3, 1.5)) == 1  # not whole: tenths
    assert frames.labels(frames.times(6, 2, start=seconds("0:02.5"))) == 1  # a window off the second keeps tenths


def test_main_and_zoom_sheets_label_the_same_moment_alike(tmp_path, video):
    main = frames.build(video, tmp_path / "m", every=1)
    zoom = frames.build(video, tmp_path / "z", every=0.2, start=2, end=3)
    assert main["sheets"][0]["tiles"][:2] == ["00:01", "00:02"] and zoom["sheets"][0]["tiles"][0] == "00:02.0"
