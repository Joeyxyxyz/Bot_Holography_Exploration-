"""
Scan the curved edges from a calibration sweep: per DMD column, how clean is its light sheet in the liquid?

For each column frame (background subtracted, inside the liquid ROI) and each camera row, take the
intensity-weighted x centroid and spread of the glow. A column entering a FLAT face gives one narrow line
whose centroid moves smoothly with height; a column hitting a ROUNDED edge is refracted over a range of
angles and gives a wide, bent or split band. Reported per column:
  energy        total glow (normalised)
  spread_px     median per-row RMS width of the glow
  bend_px       RMS residual of a straight-line fit of centroid vs row
  quality       1 for the cleanest columns, falling toward 0 for wide / bent / dim ones
  python -m vol2.edge_quality <calib_run_dir> [--roi x0 y0 x1 y1]
[PROVED as image measurements; the clean/curved threshold is a HEURISTIC choice.]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def column_metrics(img, min_frac=0.15):
    rows = []
    thr = min_frac * float(img.max()) if img.max() > 0 else 0.0
    for y in range(img.shape[0]):
        r = img[y]
        w = np.where(r > thr, r, 0.0)
        s = w.sum()
        if s <= 0:
            continue
        x = np.arange(len(r))
        cx = (w * x).sum() / s
        sp = np.sqrt((w * (x - cx) ** 2).sum() / s)
        rows.append((y, cx, sp, s))
    if len(rows) < 10:
        return None
    a = np.array(rows)
    p = np.polyfit(a[:, 0], a[:, 1], 1, w=np.sqrt(a[:, 3]))
    bend = float(np.sqrt(np.average((a[:, 1] - np.polyval(p, a[:, 0])) ** 2, weights=a[:, 3])))
    return {"spread_px": float(np.median(a[:, 2])), "bend_px": bend, "rows_lit": int(len(a))}


def analyse(run: Path, roi):
    z = np.load(run / "raw.npz")
    black = np.mean([z[k].astype(np.float32) for k in z.files if k.startswith("black")], axis=0)
    x0, y0, x1, y1 = roi
    cols = sorted((k for k in z.files if k.startswith("col_")), key=lambda k: int(k.split("_")[1]))
    out = []
    for k in cols:
        img = np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1]
        img = cv2.GaussianBlur(img, (0, 0), 1.0)
        m = column_metrics(img)
        e = float(img.sum())
        out.append({"col": int(k.split("_")[1]), "energy": e, **(m or {"spread_px": None, "bend_px": None})})
    E = max(o["energy"] for o in out) or 1.0
    good = [o for o in out if o["spread_px"] is not None and o["energy"] > 0.3 * E]
    sp0 = np.percentile([o["spread_px"] for o in good], 25) if good else 1.0
    bd0 = np.percentile([o["bend_px"] for o in good], 25) if good else 1.0
    for o in out:
        o["energy"] = round(o["energy"] / E, 3)
        if o["spread_px"] is None or o["energy"] < 0.3:
            o["quality"] = 0.0
            continue
        q = min(1.0, sp0 / o["spread_px"]) * min(1.0, (bd0 + 1.0) / (o["bend_px"] + 1.0))
        o["quality"] = round(float(q), 3)
        o["spread_px"] = round(o["spread_px"], 2)
        o["bend_px"] = round(o["bend_px"], 2)
    # strip chart: energy (top) and quality (bottom) vs column
    W, Hh = 900, 300
    img = np.zeros((Hh, W), np.uint8)
    xs = np.array([o["col"] for o in out], float)
    u = ((xs - xs.min()) / max(xs.max() - xs.min(), 1) * (W - 20) + 10).astype(int)
    for key, top in (("energy", 10), ("quality", 160)):
        v = np.array([o[key] for o in out], float)
        pts = np.stack([u, (top + 130 - v * 130).astype(int)], 1).astype(np.int32)
        cv2.polylines(img, [pts], False, 255, 1)
        cv2.putText(img, key, (12, top + 14), cv2.FONT_HERSHEY_PLAIN, 1.0, 255, 1)
    for c in range(int(xs.min()) // 20 * 20, int(xs.max()) + 1, 20):
        x = int((c - xs.min()) / max(xs.max() - xs.min(), 1) * (W - 20) + 10)
        cv2.line(img, (x, 290), (x, 296), 255, 1)
        if c % 40 == 0:
            cv2.putText(img, str(c), (x - 12, 288), cv2.FONT_HERSHEY_PLAIN, 0.8, 255, 1)
    cv2.imwrite(str(run / "edge_quality.png"), img)
    (run / "edge_quality.json").write_text(json.dumps({"roi": roi, "columns": out}, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--roi", type=int, nargs=4, default=[500, 455, 790, 710])
    a = ap.parse_args()
    res = analyse(a.run, tuple(a.roi))
    print(" ".join(f"{o['col']}:{o['quality']:.2f}" for o in res))
