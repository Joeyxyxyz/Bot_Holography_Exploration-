"""
Before/after: a flat full-width plane (fixed row, the uncorrected design) vs the warp-corrected plane (row per
column from warp_scan, so the camera sees one level straight line). Same columns, same thickness, blue.
Straightness = RMS of the glow line's camera y about its best straight line, and its slope.
  python -m vol2.warp_test <warp_scan_run> [--row 972]
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
from vol2.warp_scan import corrected_plane_rows  # noqa: E402

H, W = 1140, 912


def frame(cols, rows, thick=8):
    f = np.zeros((H, W, 3), np.uint8)
    for c, r in zip(cols, np.round(rows).astype(int)):
        f[r - thick // 2:r + thick - thick // 2, c, 0] = 255
    return f


def line_stats(d, x0, x1):
    d = cv2.GaussianBlur(d, (0, 0), 2)
    xs, ys = [], []
    for x in range(x0, x1):
        col = d[:, x]
        if col.max() < 8:
            continue
        y = int(np.argmax(col))
        lo, hi = max(0, y - 12), y + 12
        w = col[lo:hi]
        ys.append(float((w * np.arange(lo, hi)).sum() / w.sum()))
        xs.append(x)
    if len(xs) < 10:
        return None
    xs, ys = np.array(xs), np.array(ys)
    p = np.polyfit(xs, ys, 1)
    res = ys - np.polyval(p, xs)
    return {"slope": round(float(p[0]), 4), "rms_px": round(float(np.sqrt(np.mean(res ** 2))), 2),
            "p95_px": round(float(np.percentile(np.abs(res), 95)), 2), "n": int(len(xs))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("warp_run", type=Path)
    ap.add_argument("--row", type=float, default=972)
    a = ap.parse_args()
    cols, rows_corr, y0 = corrected_plane_rows(a.warp_run, a.row)
    fr = {"flat": frame(cols, np.full(len(cols), a.row)), "corrected": frame(cols, rows_corr)}
    from rig import bench as vm
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_warp_test")
    run.mkdir(parents=True)
    lock, sync = vm.open_rig()
    shots = {}
    try:
        sync.camera.set_exposure_us(200000)
        shots["black"] = sync.shoot(np.zeros((H, W, 3), np.uint8), raw=True).astype(np.float32)
        for k, f in fr.items():
            shots[k] = sync.shoot(f, raw=True).astype(np.float32)
            cv2.imwrite(str(run / f"dmd_{k}.png"), f)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    w = np.load(a.warp_run / "warp_map.npz")
    X = w["X"]
    x0, x1 = int(np.nanpercentile(X, 2)), int(np.nanpercentile(X, 98))
    rep = {"warp_run": str(a.warp_run), "design_row": a.row, "target_camera_y": y0,
           "cols": [int(cols[0]), int(cols[-1])], "row_range_corrected": [float(rows_corr.min()), float(rows_corr.max())]}
    tiles = []
    for k in fr:
        d = np.clip(shots[k] - shots["black"], 0, None)
        rep[k] = line_stats(d, x0, x1)
        a_ = d[int(y0) - 120:int(y0) + 120, max(0, x0 - 60):x1 + 60]
        a_ = (np.clip(a_ / max(np.percentile(a_, 99.8), 1), 0, 1) ** 0.6 * 255).astype(np.uint8)
        a_ = cv2.cvtColor(a_, cv2.COLOR_GRAY2BGR)
        cv2.line(a_, (0, 120), (a_.shape[1] - 1, 120), (0, 0, 255), 1)          # the target level line
        cv2.putText(a_, f"{k}: rms {rep[k]['rms_px'] if rep[k] else '-'} px, slope {rep[k]['slope'] if rep[k] else '-'}",
                    (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        tiles.append(a_)
    cv2.imwrite(str(run / "before_after.png"), np.vstack(tiles))
    np.savez_compressed(run / "raw.npz", **{k: v.astype(np.float16) for k, v in shots.items()})
    (run / "warp_test.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
