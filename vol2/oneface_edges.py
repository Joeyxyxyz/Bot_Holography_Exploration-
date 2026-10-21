"""
One-face edge scan (2026-10-05 evening, case right side up, projecting into a single flat face).

  python -m vol2.oneface_edges capture [--exp 66667]
  python -m vol2.oneface_edges analyse <run> [--roi x0 y0 x1 y1]

capture: blue-only (raw BGR, HDMI video mode, no LED change), rig lock via rig.bench.open_rig()
  floods : window 9-12 x F-J (600-712 x 722-967) and a wide face flood (560-790 x 650-1065)
  cols   : 2-mirror-wide column sheets every 2nd column 590..722, rows 700..990
  rows   : 3-mirror-tall row lines every 4th row 700..988, cols 600..712
analyse: per column sheet -> camera x-centroid per camera row, spread, bend (edge_quality.column_metrics),
  and the mean camera x vs DMD col (local slope: refraction at a rounded edge bends this mapping);
  per row line the same transposed. Clean window = longest run with quality >= q_min and slope within
  +-30 % of the median slope. [measurements PROVED; thresholds HEURISTIC]
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
from vol2.edge_quality import column_metrics  # noqa: E402

H, W = 1140, 912
COLS = (590, 722, 2)
COL_ROWS = (700, 990)
ROWS = (700, 988, 4)
ROW_COLS = (600, 712)
CELL_COL0, CELL_W = 376, 28
ROW_EDGES = [477, 526, 575, 624, 673, 722, 771, 820, 869, 918, 967, 1016, 1065, 1114]


def cell_col(c):
    return 1 + int((c - CELL_COL0) // CELL_W)


def cell_row(r):
    for i in range(len(ROW_EDGES) - 1):
        if ROW_EDGES[i] <= r < ROW_EDGES[i + 1]:
            return "ABCDEFGHIJKLM"[i]
    return "?"


def frames():
    out = [("black_0", np.zeros((H, W), np.uint8))]
    f = np.zeros((H, W), np.uint8); f[722:967, 600:712] = 255; out.append(("flood_win", f))
    f = np.zeros((H, W), np.uint8); f[650:1065, 560:790] = 255; out.append(("flood_wide", f))
    out.append(("black_1", np.zeros((H, W), np.uint8)))
    for c in range(COLS[0], COLS[1] + 1, COLS[2]):
        f = np.zeros((H, W), np.uint8); f[COL_ROWS[0]:COL_ROWS[1], c:c + 2] = 255
        out.append((f"col_{c}", f))
    out.append(("black_2", np.zeros((H, W), np.uint8)))
    for r in range(ROWS[0], ROWS[1] + 1, ROWS[2]):
        f = np.zeros((H, W), np.uint8); f[r:r + 3, ROW_COLS[0]:ROW_COLS[1]] = 255
        out.append((f"row_{r}", f))
    out.append(("black_3", np.zeros((H, W), np.uint8)))
    return out


def capture(exp=66667):
    from rig import bench as vm
    fr = frames()
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_oneface_edges")
    run.mkdir(parents=True)
    vm.DUTY = 1.0
    lock, sync = vm.open_rig()
    shots = {}
    t0 = time.time()
    try:
        sync.camera.set_exposure_us(exp)
        for name, f in fr:
            img = sync.shoot(np.dstack([f, f * 0, f * 0]).astype(np.uint8), raw=True)
            shots[name] = img.astype(np.float16)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **shots)
    (run / "meta.json").write_text(json.dumps({"color": "blue", "exposure_us": exp, "n": len(fr),
        "cols": COLS, "col_rows": COL_ROWS, "rows": ROWS, "row_cols": ROW_COLS, "seconds": round(time.time() - t0, 1),
        "setup": "case right side up, single flat face toward projector (Joey 2026-10-05 20:13)",
        "note": "blue HDMI frames, raw camera, no LED change, no USB"}, indent=1))
    print(run, flush=True)
    return run


def stretch(img, lo=1, hi=99.7, g=0.6):
    a, b = np.percentile(img, lo), np.percentile(img, hi)
    x = np.clip((img - a) / max(b - a, 1e-6), 0, 1) ** g
    return (x * 255).astype(np.uint8)


def _clean_run(xs, ok):
    best, cur = (None, None, 0), None
    for x, o in zip(xs, ok):
        if o:
            cur = (cur[0] if cur else x, x)
            n = (cur[1] - cur[0])
            if n >= best[2]:
                best = (cur[0], cur[1], n)
        else:
            cur = None
    return best[:2]


def analyse_set(z, black, keys, roi, axis):
    x0, y0, x1, y1 = roi
    res = []
    for k in keys:
        img = np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1]
        img = cv2.GaussianBlur(img, (0, 0), 1.0)
        im = img if axis == "col" else img.T
        m = column_metrics(im)
        e = float(img.sum())
        tot = im.sum(0)
        cpos = float((tot * np.arange(len(tot))).sum() / tot.sum()) if tot.sum() > 0 else None
        res.append({"dmd": int(k.split("_")[1]), "energy": e, "cam_pos": None if cpos is None else
                    cpos + (x0 if axis == "col" else y0), **(m or {"spread_px": None, "bend_px": None})})
    E = max(o["energy"] for o in res) or 1.0
    good = [o for o in res if o["spread_px"] is not None and o["energy"] > 0.3 * E]
    sp0 = np.percentile([o["spread_px"] for o in good], 25) if good else 1.0
    bd0 = np.percentile([o["bend_px"] for o in good], 25) if good else 1.0
    for o in res:
        o["energy"] = round(o["energy"] / E, 3)
        if o["spread_px"] is None or o["energy"] < 0.3:
            o["quality"] = 0.0
        else:
            o["quality"] = round(float(min(1.0, sp0 / o["spread_px"]) * min(1.0, (bd0 + 1.0) / (o["bend_px"] + 1.0))), 3)
    d = np.array([o["dmd"] for o in res], float)
    p = np.array([o["cam_pos"] if o["cam_pos"] is not None else np.nan for o in res], float)
    sl = np.gradient(p, d)
    med = np.nanmedian(sl[[o["quality"] >= 0.5 for o in res]]) if any(o["quality"] >= 0.5 for o in res) else np.nanmedian(sl)
    for o, s in zip(res, sl):
        o["slope_cam_per_dmd"] = None if not np.isfinite(s) else round(float(s), 3)
        o["slope_ratio"] = None if not np.isfinite(s) else round(float(s / med), 3)
    return res, float(med)


def analyse(run: Path, roi=None, q_min=0.55):
    z = np.load(run / "raw.npz")
    black = np.mean([z[k].astype(np.float32) for k in z.files if k.startswith("black")], axis=0)
    ck = sorted((k for k in z.files if k.startswith("col_")), key=lambda k: int(k.split("_")[1]))
    rk = sorted((k for k in z.files if k.startswith("row_")), key=lambda k: int(k.split("_")[1]))
    fl = np.clip(z["flood_win"].astype(np.float32) - black, 0, None)
    if roi is None:
        acc = np.max([np.clip(z[k].astype(np.float32) - black, 0, None) for k in ck + rk], axis=0)
        acc = cv2.GaussianBlur(acc, (0, 0), 3)
        m = acc > 0.15 * np.percentile(acc, 99.9)
        ys, xs = np.nonzero(m)
        roi = (int(np.percentile(xs, 0.5)) - 10, int(np.percentile(ys, 0.5)) - 10,
               int(np.percentile(xs, 99.5)) + 10, int(np.percentile(ys, 99.5)) + 10)
    roi = tuple(int(v) for v in roi)
    cres, cmed = analyse_set(z, black, ck, roi, "col")
    rres, rmed = analyse_set(z, black, rk, roi, "row")

    def ok(o):
        return o["quality"] >= q_min and o["slope_ratio"] is not None and 0.7 <= o["slope_ratio"] <= 1.3
    cw = _clean_run([o["dmd"] for o in cres], [ok(o) for o in cres])
    rw = _clean_run([o["dmd"] for o in rres], [ok(o) for o in rres])
    rep = {"run": str(run), "roi": roi, "q_min": q_min, "median_slope_cols": cmed, "median_slope_rows": rmed,
           "clean_cols": cw, "clean_rows": rw,
           "clean_cells": None if None in cw or None in rw else
           f"cols {cell_col(cw[0])}-{cell_col(cw[1] + 1)} x rows {cell_row(rw[0])}-{cell_row(rw[1] + 2)}",
           "columns": cres, "rows": rres}
    (run / "edges.json").write_text(json.dumps(rep, indent=1))
    # contact sheet: flood + every 3rd column sheet + every 3rd row line, ROI crops
    x0, y0, x1, y1 = roi
    tiles = []
    def tile(k, label):
        img = np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1]
        t = cv2.resize(stretch(img), (220, int(220 * (y1 - y0) / max(x1 - x0, 1))))
        t = cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)
        cv2.putText(t, label, (4, 14), cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 255, 255), 1)
        return t
    tiles.append(tile("flood_win", "flood 9-12xF-J")); tiles.append(tile("flood_wide", "flood wide"))
    for o in cres[::3]:
        tiles.append(tile(f"col_{o['dmd']}", f"c{o['dmd']} q{o['quality']:.2f} s{o['slope_ratio']}"))
    for o in rres[::3]:
        tiles.append(tile(f"row_{o['dmd']}", f"r{o['dmd']} q{o['quality']:.2f} s{o['slope_ratio']}"))
    n = 8
    th, tw = tiles[0].shape[:2]
    while len(tiles) % n:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[i:i + n]) for i in range(0, len(tiles), n)])
    cv2.imwrite(str(run / "contact_sheet.png"), sheet)
    # overlay: centroid traces of clean (green) vs not (red) column sheets and row lines on the flood
    ov = cv2.cvtColor(stretch(fl), cv2.COLOR_GRAY2BGR)
    for o, k in zip(cres, ck):
        img = np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1]
        img = cv2.GaussianBlur(img, (0, 0), 1.0)
        thr = 0.15 * img.max()
        col = (0, 255, 0) if ok(o) else (0, 0, 255)
        for y in range(0, img.shape[0], 3):
            r = np.where(img[y] > thr, img[y], 0)
            if r.sum() > 0:
                cx = (r * np.arange(len(r))).sum() / r.sum()
                cv2.circle(ov, (int(cx + x0), y + y0), 1, col, -1)
    for o, k in zip(rres, rk):
        img = np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1]
        img = cv2.GaussianBlur(img, (0, 0), 1.0)
        thr = 0.15 * img.max()
        col = (255, 255, 0) if ok(o) else (255, 0, 255)
        for x in range(0, img.shape[1], 3):
            c = np.where(img[:, x] > thr, img[:, x], 0)
            if c.sum() > 0:
                cy = (c * np.arange(len(c))).sum() / c.sum()
                cv2.circle(ov, (x + x0, int(cy + y0)), 1, col, -1)
    cv2.rectangle(ov, (x0, y0), (x1, y1), (128, 128, 128), 1)
    cv2.imwrite(str(run / "overlay_traces.png"), ov[max(0, y0 - 60):y1 + 60, max(0, x0 - 60):x1 + 60])
    print(json.dumps({k: rep[k] for k in ("roi", "clean_cols", "clean_rows", "clean_cells",
                                          "median_slope_cols", "median_slope_rows")}))
    print("cols", " ".join(f"{o['dmd']}:{o['quality']:.2f}/{o['slope_ratio']}/{o['energy']}" for o in cres))
    print("rows", " ".join(f"{o['dmd']}:{o['quality']:.2f}/{o['slope_ratio']}/{o['energy']}" for o in rres))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture"); c.add_argument("--exp", type=int, default=66667)
    a = sub.add_parser("analyse"); a.add_argument("run", type=Path); a.add_argument("--roi", type=int, nargs=4)
    a.add_argument("--qmin", type=float, default=0.55)
    args = ap.parse_args()
    if args.cmd == "capture":
        capture(args.exp)
    else:
        analyse(args.run, args.roi, args.qmin)
