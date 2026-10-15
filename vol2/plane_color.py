"""
How far does each colour carry into the fluorescent glycerin? (Joey: stronger, flatter plane; white edging
to get the light in further.)

Projects the same flat plane (both faces, every column of the clean windows, a band of rows at mid-height)
in blue / green / red / cyan / white / blue-core + white edges / blue-core + green edges, and photographs each
through face A. The plane is seen nearly edge-on as a horizontal band; its glow profile ALONG the band (camera x)
shows how far into the liquid the light keeps glowing. Colour = raw BGR frame channels (which LED sub-frames
the mirrors are on in); LED currents are not touched.

  python -m vol2.plane_color            # capture + analyse
  python -m vol2.plane_color --analyse <run>
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
WIN_A, WIN_B = (588, 643), (697, 748)
R_MID, CORE, EDGE = 972, 6, 4                 # mid-height row, core rows, edge rows above and below


def plane(core_bgr, edge_bgr=None):
    f = np.zeros((H, W, 3), np.uint8)
    r0, r1 = R_MID - CORE // 2, R_MID + CORE - CORE // 2
    for c0, c1 in (WIN_A, WIN_B):
        f[r0:r1, c0:c1 + 1] = core_bgr
        if edge_bgr is not None:
            f[r0 - EDGE:r0, c0:c1 + 1] = edge_bgr
            f[r1:r1 + EDGE, c0:c1 + 1] = edge_bgr
    return f


VARIANTS = {
    "blue": plane((255, 0, 0)), "green": plane((0, 255, 0)), "red": plane((0, 0, 255)),
    "cyan": plane((255, 255, 0)), "white": plane((255, 255, 255)),
    "blue_whiteedge": plane((255, 0, 0), (255, 255, 255)), "blue_greenedge": plane((255, 0, 0), (0, 255, 0)),
}


def capture(exps=(66667, 200000)):
    from rig import bench as vm
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_plane_color")
    run.mkdir(parents=True)
    lock, sync = vm.open_rig()
    shots = {}
    try:
        for exp in exps:
            sync.camera.set_exposure_us(exp)
            shots[f"black_{exp}"] = sync.shoot(np.zeros((H, W, 3), np.uint8), raw=True).astype(np.float32)
            for name, fr in VARIANTS.items():
                shots[f"{name}_{exp}"] = sync.shoot(fr, raw=True).astype(np.float32)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **{k: v.astype(np.float16) for k, v in shots.items()})
    for k, fr in VARIANTS.items():
        cv2.imwrite(str(run / f"dmd_{k}.png"), fr)
    return run


def analyse(run: Path, exp=200000):
    z = np.load(run / "raw.npz")
    b = z[f"black_{exp}"].astype(np.float32)
    diffs = {k: np.clip(z[f"{k}_{exp}"].astype(np.float32) - b, 0, None) for k in VARIANTS}
    # band rows: where the blue plane glows most (camera y), +/- 25 px
    prof_y = cv2.GaussianBlur(diffs["blue"], (0, 0), 3).sum(axis=1)
    yc = int(np.argmax(prof_y))
    band = slice(max(0, yc - 25), yc + 25)
    rep = {"band_rows_camera": [band.start, band.stop], "variants": {}}
    curves = {}
    for k, d in diffs.items():
        x = cv2.GaussianBlur(d, (0, 0), 3)[band].sum(axis=0)
        curves[k] = x
        lit = x > 0.1 * x.max() if x.max() > 0 else np.zeros_like(x, bool)
        xs = np.nonzero(lit)[0]
        rep["variants"][k] = {"total": float(x.sum()), "peak": float(x.max()),
                              "extent_px_10pct": int(xs.max() - xs.min()) if len(xs) else 0,
                              "x_range_10pct": [int(xs.min()), int(xs.max())] if len(xs) else None}
    tot_b = rep["variants"]["blue"]["total"] or 1.0
    for k in rep["variants"]:
        rep["variants"][k]["total_rel_blue"] = round(rep["variants"][k]["total"] / tot_b, 3)
    # plot: profiles along the band, and a montage of the crops
    Wp, Hp = 1000, 360
    img = np.zeros((Hp, Wp, 3), np.uint8)
    col = {"blue": (255, 120, 0), "green": (0, 220, 0), "red": (0, 0, 255), "cyan": (255, 255, 0),
           "white": (255, 255, 255), "blue_whiteedge": (200, 160, 255), "blue_greenedge": (120, 255, 160)}
    top = max(c.max() for c in curves.values()) or 1.0
    for i, (k, c) in enumerate(curves.items()):
        xs = np.linspace(0, Wp - 1, len(c)).astype(int)
        pts = np.stack([xs, (Hp - 20 - c / top * (Hp - 40)).astype(int)], 1).astype(np.int32)
        cv2.polylines(img, [pts], False, col[k], 1)
        cv2.putText(img, k, (10, 18 + 16 * i), cv2.FONT_HERSHEY_PLAIN, 1.0, col[k], 1)
    cv2.imwrite(str(run / "profiles.png"), img)
    tiles = []
    for k, d in diffs.items():
        a = d[max(0, yc - 140):yc + 140, 380:940]
        a = (np.clip(a / max(np.percentile(diffs["white"], 99.9), 1), 0, 1) ** 0.6 * 255).astype(np.uint8)
        a = cv2.resize(a, (420, 210))
        cv2.putText(a, k, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 255, 2)
        tiles.append(a)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(run / "montage.png"), np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]))
    (run / "plane_color.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyse", type=Path)
    a = ap.parse_args()
    analyse(a.analyse if a.analyse else capture())
