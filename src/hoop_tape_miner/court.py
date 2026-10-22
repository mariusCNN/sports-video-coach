"""FIBA court model and court-line based homography refinement.

Court coordinates are metres: x along the length (0 = left baseline, 28 = right
baseline as seen from the camera), y across the width (0 = near sideline on the
camera side, 15 = far sideline).
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.optimize import least_squares

LENGTH, WIDTH = 28.0, 15.0
HOOP_FROM_BASELINE = 1.575
THREE_PT_RADIUS = 6.75
THREE_PT_SIDE = 0.9  # straight 3pt segment distance from sideline
LANE_WIDTH = 4.9
FT_LINE = 5.8
CENTER_CIRCLE_R = 1.8
RESTRICTED_R = 1.25


def hoop_xy(side: str) -> tuple[float, float]:
    return (HOOP_FROM_BASELINE, WIDTH / 2) if side == "left" else (LENGTH - HOOP_FROM_BASELINE, WIDTH / 2)


def _arc(cx, cy, r, a0, a1, n):
    t = np.linspace(a0, a1, n)
    return np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], 1)


def _seg(p, q, step=0.1):
    p, q = np.asarray(p, float), np.asarray(q, float)
    n = max(2, int(np.linalg.norm(q - p) / step))
    return np.linspace(p, q, n)


def court_polylines() -> list[np.ndarray]:
    """All court markings as dense polylines (metres)."""
    L, W = LENGTH, WIDTH
    lines = [
        _seg((0, 0), (L, 0)), _seg((0, W), (L, W)),
        _seg((0, 0), (0, W)), _seg((L, 0), (L, W)),
        _seg((L / 2, 0), (L / 2, W)),
        _arc(L / 2, W / 2, CENTER_CIRCLE_R, 0, 2 * np.pi, 120),
    ]
    for side in ("left", "right"):
        hx, hy = hoop_xy(side)
        s = 1 if side == "left" else -1
        bx = 0 if side == "left" else L
        y0, y1 = (W - LANE_WIDTH) / 2, (W + LANE_WIDTH) / 2
        ftx = bx + s * FT_LINE
        lines += [_seg((bx, y0), (ftx, y0)), _seg((bx, y1), (ftx, y1)), _seg((ftx, y0), (ftx, y1))]
        # free-throw circle (outer half solid, inner half dashed -> only outer)
        a = np.pi / 2
        lines.append(_arc(ftx, W / 2, 1.8, -a, a, 60) if side == "left" else _arc(ftx, W / 2, 1.8, a, 3 * a, 60))
        # three point line: straight parts + arc
        ys, ye = THREE_PT_SIDE, W - THREE_PT_SIDE
        dy = W / 2 - ys
        dx = np.sqrt(THREE_PT_RADIUS ** 2 - dy ** 2)
        lines += [_seg((bx, ys), (hx + s * dx, ys)), _seg((bx, ye), (hx + s * dx, ye))]
        ang = np.arcsin(dy / THREE_PT_RADIUS)
        if side == "left":
            lines.append(_arc(hx, hy, THREE_PT_RADIUS, -ang, ang, 200))
        else:
            lines.append(_arc(hx, hy, THREE_PT_RADIUS, np.pi - ang, np.pi + ang, 200))
    return lines


COURT_POINTS = np.concatenate(court_polylines())


def project(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    return p[:, :2] / p[:, 2:3]


def white_line_mask(bgr: np.ndarray) -> np.ndarray:
    """Thin bright low-saturation structures (court paint), suppressing wide glare."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2]
    tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    m = ((tophat > 40) & (hsv[..., 1] < 60)).astype(np.uint8)
    # drop speckle from parquet texture: keep only elongated / large components
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    bw, bh, area = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT], stats[:, cv2.CC_STAT_AREA]
    keep = (np.maximum(bw, bh) >= 25) & (area >= 25)
    keep[0] = False
    return (keep[lab]).astype(np.uint8) * 255


def floor_mask(bgr: np.ndarray, H_court2img: np.ndarray, margin=1.5) -> np.ndarray:
    """Polygon of the playing floor (+margin) in image space."""
    poly = np.array([[-margin, -margin], [LENGTH + margin, -margin], [LENGTH + margin, WIDTH + margin], [-margin, WIDTH + margin]])
    dense = np.concatenate([_seg(poly[i], poly[(i + 1) % 4], 0.5) for i in range(4)])
    pi = project(H_court2img, dense)
    m = np.zeros(bgr.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.round(pi).astype(np.int32)], 255)
    return m


def refine_homography(bgr: np.ndarray, H0: np.ndarray, ignore_mask: np.ndarray | None = None,
                      max_dist=25.0, iters=2) -> tuple[np.ndarray, float, int]:
    """Refine court->image homography by aligning projected court lines with painted lines.

    Returns (H, median residual px, number of supporting points).
    """
    mask = white_line_mask(bgr)
    if ignore_mask is not None:
        mask[ignore_mask > 0] = 0
    dt, labels = cv2.distanceTransformWithLabels(255 - mask, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    h, w = mask.shape
    ys, xs = np.nonzero(mask == 255)
    # map labels -> nearest line pixel coordinates
    lab_xy = np.zeros((labels.max() + 1, 2), np.float32)
    zero_pts = np.argwhere(255 - mask == 0)
    lab_ids = labels[zero_pts[:, 0], zero_pts[:, 1]]
    lab_xy[lab_ids] = zero_pts[:, ::-1]

    H = H0 / H0[2, 2]
    support, med = 0, 999.0
    for it in range(iters):
        pi = project(H, COURT_POINTS)
        ok = (pi[:, 0] >= 0) & (pi[:, 0] < w - 1) & (pi[:, 1] >= 0) & (pi[:, 1] < h - 1)
        src = COURT_POINTS[ok]
        pii = np.round(pi[ok]).astype(int)
        d = dt[pii[:, 1], pii[:, 0]]
        thr = max_dist if it == 0 else max_dist * 0.5
        keep = d < thr
        if keep.sum() < 30:
            return H, 999.0, int(keep.sum())
        src = src[keep]
        tgt = lab_xy[labels[pii[keep, 1], pii[keep, 0]]]

        def resid(p):
            Hp = np.append(p, 1.0).reshape(3, 3)
            return (project(Hp, src) - tgt).ravel()

        r = least_squares(resid, H.ravel()[:8], loss="huber", f_scale=3.0, max_nfev=200)
        H = np.append(r.x, 1.0).reshape(3, 3)
        res = np.linalg.norm(r.fun.reshape(-1, 2), axis=1)
        med = float(np.median(res))
        support = int((res < 4).sum())
    return H, med, support


def draw_court_overlay(bgr: np.ndarray, H: np.ndarray, color=(255, 0, 255)) -> np.ndarray:
    out = bgr.copy()
    for pl in court_polylines():
        pi = project(H, pl)
        cv2.polylines(out, [np.round(pi).astype(np.int32)], False, color, 2)
    return out
