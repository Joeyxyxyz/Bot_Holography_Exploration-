"""
Scan how the case bends projected light (Joey: face B takes the light fairly straight; face A, toward the camera,
bends straight lines to the right; the far corner of A bends hardest), then pre-warp content so it looks straight
from the viewing position (the camera).

capture : one small mirror block at a time on a grid over the full width (both faces, the corner, both outer
          edges) and the liquid height; the camera records where each lands (glow centroid). Rig lock held.
analyse : grid of camera positions f(c, r) -> (x, y); a picture of the bent grid; per-column row correction
          that makes a horizontal plane come out as a straight horizontal line in the camera image.
  python -m vol2.warp_scan capture [--step-c 10 --step-r 20]
  python -m vol2.warp_scan analyse <run>
The correction is viewer-dependent by nature (it straightens what the camera sees). [PROVED as measurement]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
H, W = 1140, 912
COLS = (560, 785)
ROWS = (860, 1090)


def dot(c, r, wc=3, wr=5, level=255):
    f = np.zeros((H, W, 3), np.uint8)
    f[r - wr // 2:r + wr // 2 + 1, c - wc // 2:c + wc // 2 + 1, 0] = level
    return f


def capture(step_c=10, step_r=20, exp=200000):
    from rig import bench as vm
    cs = list(range(COLS[0], COLS[1] + 1, step_c))
    rs = list(range(ROWS[0], ROWS[1] + 1, step_r))
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_warp_scan")
    run.mkdir(parents=True)
    lock, sync = vm.open_rig()
    shots = {}
    try:
        sync.camera.set_exposure_us(exp)
        shots["black"] = sync.shoot(np.zeros((H, W, 3), np.uint8), raw=True).astype(np.float32)
        for r in rs:
            for c in cs:
                shots[f"d_{c}_{r}"] = sync.shoot(dot(c, r), raw=True).astype(np.float16)
            print(f"  row {r} done", flush=True)
        shots["black2"] = sync.shoot(np.zeros((H, W, 3), np.uint8), raw=True).astype(np.float32)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **{k: np.asarray(v, np.float16) for k, v in shots.items()})
    (run / "meta.json").write_text(json.dumps({"cols": cs, "rows": rs, "exposure_us": exp}, indent=1))
    return run


def analyse(run: Path):
    z = np.load(run / "raw.npz")
    meta = json.loads((run / "meta.json").read_text())
    cs, rs = meta["cols"], meta["rows"]
    black = 0.5 * (z["black"].astype(np.float32) + z["black2"].astype(np.float32))
    X = np.full((len(rs), len(cs)), np.nan)
    Y = np.full((len(rs), len(cs)), np.nan)
    E = np.zeros((len(rs), len(cs)))
    for i, r in enumerate(rs):
        for j, c in enumerate(cs):
            d = cv2.GaussianBlur(np.clip(z[f"d_{c}_{r}"].astype(np.float32) - black, 0, None), (0, 0), 2)
            pk = d.max()
            if pk < 6:
                continue
            m = d > 0.5 * pk                       # the bright core of the dot's glow
            n, lab, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
            k = 1 + int(np.argmax([d[lab == q].sum() for q in range(1, n)])) if n > 1 else 0
            if k == 0:
                continue
            w = np.where(lab == k, d, 0)
            ys, xs = np.mgrid[0:d.shape[0], 0:d.shape[1]]
            X[i, j] = (w * xs).sum() / w.sum()
            Y[i, j] = (w * ys).sum() / w.sum()
            E[i, j] = w.sum()
    # straightness of each DMD row as seen by the camera: residual of a straight-line fit y(x)
    row_bend = []
    for i, r in enumerate(rs):
        ok = np.isfinite(X[i]) & np.isfinite(Y[i])
        if ok.sum() >= 4:
            p = np.polyfit(X[i, ok], Y[i, ok], 1)
            res = Y[i, ok] - np.polyval(p, X[i, ok])
            row_bend.append({"row": r, "slope": round(float(p[0]), 4), "rms_px": round(float(np.sqrt(np.mean(res ** 2))), 2),
                             "max_px": round(float(np.max(np.abs(res))), 2)})
    # correction: for each column, the row whose camera y equals the target line y0 (the median camera y of
    # the plane's design row), by interpolating y(r) down that column
    y_of = {}
    for j, c in enumerate(cs):
        ok = np.isfinite(Y[:, j])
        if ok.sum() >= 3:
            y_of[c] = (np.array(rs)[ok], Y[ok, j])
    rep = {"cols": cs, "rows": rs, "found": int(np.isfinite(X).sum()), "of": len(cs) * len(rs), "row_bend": row_bend}
    (run / "warp_map.json").write_text(json.dumps({"X": np.nan_to_num(X, nan=-1).tolist(),
                                                   "Y": np.nan_to_num(Y, nan=-1).tolist(), **rep}, indent=1))
    np.savez(run / "warp_map.npz", X=X, Y=Y, E=E, cols=np.array(cs), rows=np.array(rs))
    # picture: the bent grid over a camera frame (sum of a few dots for context)
    bg = np.clip(sum(z[f"d_{cs[j]}_{rs[i]}"].astype(np.float32) for i in range(0, len(rs), 3)
                     for j in range(0, len(cs), 3)) - black * 0, 0, 255)
    img = cv2.cvtColor((np.clip(bg / max(np.percentile(bg, 99.5), 1), 0, 1) * 160).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for i in range(len(rs)):
        pts = [(int(X[i, j]), int(Y[i, j])) for j in range(len(cs)) if np.isfinite(X[i, j])]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, (0, 200, 255), 1)
    for j in range(len(cs)):
        pts = [(int(X[i, j]), int(Y[i, j])) for i in range(len(rs)) if np.isfinite(X[i, j])]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, (255, 160, 0), 1)
    for i in range(len(rs)):
        for j in range(len(cs)):
            if np.isfinite(X[i, j]):
                cv2.circle(img, (int(X[i, j]), int(Y[i, j])), 2, (255, 255, 255), -1)
    ys, xs = np.nonzero(np.isfinite(X))
    if len(xs):
        x0, x1 = int(np.nanmin(X)) - 40, int(np.nanmax(X)) + 40
        y0, y1 = int(np.nanmin(Y)) - 40, int(np.nanmax(Y)) + 40
        crop = img[max(0, y0):y1, max(0, x0):x1]
        cv2.imwrite(str(run / "warp_grid.png"), cv2.resize(crop, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_LINEAR))
    print(json.dumps({k: rep[k] for k in ("found", "of")}), flush=True)
    for rb in row_bend:
        print(rb)
    return run


def clean_map(run: Path, max_jump_px=25.0, row_max=1030):
    """Drop glints and the far-edge jump: keep points whose camera y rises monotonically down each column and
    whose x is continuous with the column's neighbours (median of the column)."""
    w = np.load(run / "warp_map.npz")
    X, Y, cs, rs = w["X"].copy(), w["Y"].copy(), w["cols"], w["rows"]
    Y[:, :][:, :] = np.where(rs[:, None] > row_max, np.nan, Y)
    X = np.where(np.isfinite(Y), X, np.nan)
    for j in range(len(cs)):
        col = Y[:, j]
        ok = np.isfinite(col)
        if ok.sum() >= 3:
            d = np.diff(col[ok])
            med = np.nanmedian(d) if len(d) else 0
            bad = np.zeros(ok.sum(), bool)
            bad[1:] |= (d < 0.2 * med) | (d > 3 * med)
            idx = np.nonzero(ok)[0][bad]
            Y[idx, j] = np.nan
            X[idx, j] = np.nan
        xm = np.nanmedian(X[:, j]) if np.isfinite(X[:, j]).any() else np.nan
        far = np.abs(X[:, j] - xm) > max_jump_px
        X[far, j] = np.nan
        Y[far, j] = np.nan
    # main contiguous region: columns whose median x continues smoothly from their right neighbour (face B side)
    # main region = the longest run of columns whose median camera x advances smoothly. Both outer rounded edges
    # throw their dots out of order (A's far edge far to the left, B's far edge back toward the middle).
    xmed = np.array([np.nanmedian(X[:, j]) if np.isfinite(X[:, j]).any() else np.nan for j in range(len(cs))])
    d = np.diff(xmed)
    step = np.nanmedian(d[d > 0]) if np.any(d > 0) else 1.0
    good = np.isfinite(d) & (d > 0.2 * step) & (d < 3 * step)
    best, cur, best_end = 0, 0, -1
    for j, g in enumerate(good):
        cur = cur + 1 if g else 0
        if cur > best:
            best, best_end = cur, j
    keep = np.zeros(len(cs), bool)
    if best_end >= 0:
        keep[best_end - best + 1:best_end + 2] = True
    return X, Y, cs, rs, keep


def corrected_plane_rows(run: Path, design_row: float):
    """Per DMD column of the main (continuous) region, the row that puts the plane on ONE level straight line in the
    camera image (y = the design row's median camera y). Returns (columns, rows, y0)."""
    X, Y, cs, rs, keep = clean_map(run)
    i0 = int(np.argmin(np.abs(rs - design_row)))
    y0 = float(np.nanmedian(Y[i0, keep]))
    out_c, out_r = [], []
    for j, c in enumerate(cs):
        ok = np.isfinite(Y[:, j])
        if not keep[j] or ok.sum() < 3:
            continue
        yy, rr = Y[ok, j], rs[ok].astype(float)
        o = np.argsort(yy)
        if y0 < yy[o][0] - 5 or y0 > yy[o][-1] + 5:
            continue
        out_c.append(c)
        out_r.append(float(np.interp(y0, yy[o], rr[o])))
    allc = np.arange(min(out_c), max(out_c) + 1)
    return allc, np.interp(allc, out_c, out_r), y0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--step-c", type=int, default=10)
    c.add_argument("--step-r", type=int, default=20)
    a = sub.add_parser("analyse")
    a.add_argument("run", type=Path)
    args = ap.parse_args()
    if args.cmd == "capture":
        r = capture(args.step_c, args.step_r)
        analyse(r)
    else:
        analyse(args.run)
