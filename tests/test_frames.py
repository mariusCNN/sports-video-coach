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
    x, y = frames.tile_origin(n, cols, width, th)
    cell = img[y + th // 2:y + th, x + width // 2:x + width]
    return round(cell.mean() / STEP) % 32


def test_tiles_are_split_by_a_dark_gap_and_keep_the_whole_frame(tmp_path, video):
    """The gap lies between tiles, outside the frames: a fraction read off a tile is a fraction of the frame."""
    import cv2
    cols, rows, width = 3, 2, 160
    data = frames.build(video, tmp_path / "f", every=2, cols=cols, rows=rows, width=width)
    img = cv2.imread(str(tmp_path / "f" / data["sheets"][0]["file"]))
    th = round(120 * width / 160)
    assert 2 <= frames.GAP <= 4 and data["gap_px"] == frames.GAP
    assert img.shape[:2] == (rows * th + (rows - 1) * frames.GAP, cols * width + (cols - 1) * frames.GAP)
    assert frames.tile_origin(4, cols, width, th) == (width + frames.GAP, th + frames.GAP)
    gap = img[:, width:width + frames.GAP].astype(int)
    assert abs(gap.mean() - frames.GAP_BGR[0]) < 12  # the dark line, not frame pixels


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
