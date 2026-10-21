"""
Which DMD geometry makes the best flat plane in the case? (Joey: try different geometries and shapes; the
rounded corners bend light.) The rounded vertical corner acts like a cylindrical lens: a short line of light
hitting it is spread into a horizontal fan inside the liquid. Each variant is photographed through face A;
the plane is seen nearly edge-on as a band. Metrics along the band inside the case:
  coverage   fraction of the case width where the glow exceeds 25 % of the band's median-of-top-half level
  evenness   median / 90th percentile of the glow inside the case (1 = perfectly even, glints push it down)
  mean_glow  mean glow inside the case (relative to the clean blue plane)
  python -m vol2.plane_geom                # capture + analyse
  python -m vol2.plane_geom --analyse <run>
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
R = 972
BLUE, WHITE, GREEN = (255, 0, 0), (255, 255, 255), (0, 255, 0)
CASE_COLS = (560, 785)


def band(cols, r0, r1, bgr, f=None):
    f = np.zeros((H, W, 3), np.uint8) if f is None else f
    f[r0:r1, cols[0]:cols[1] + 1] = bgr
    return f


def variants():
    v = {}
    v["clean_windows"] = band((697, 748), R - 3, R + 3, BLUE, band((588, 643), R - 3, R + 3, BLUE))
    v["full_width"] = band(CASE_COLS, R - 3, R + 3, BLUE)
    v["corner_only"] = band((656, 684), R - 3, R + 3, BLUE)
    v["corner_wide"] = band((640, 700), R - 3, R + 3, BLUE)
    v["A_only"] = band((588, 655), R - 3, R + 3, BLUE)
    v["B_only"] = band((685, 760), R - 3, R + 3, BLUE)
    v["thin_2rows"] = band(CASE_COLS, R - 1, R + 1, BLUE)
    v["thick_12rows"] = band(CASE_COLS, R - 6, R + 6, BLUE)
    v["slab_40rows"] = band(CASE_COLS, R - 20, R + 20, BLUE)
    f = np.zeros((H, W, 3), np.uint8)
    for c in range(CASE_COLS[0], CASE_COLS[1] + 1):
        rr = R + int(6 * (1 if (c // 8) % 2 else -1))
        f[rr - 2:rr + 2, c] = BLUE
    v["zigzag"] = f
    f = np.zeros((H, W, 3), np.uint8)
    for c in range(CASE_COLS[0], CASE_COLS[1] + 1, 6):
        f[R - 3:R + 3, c:c + 3] = BLUE
    v["dotted_rods"] = f
    v["side_edges"] = band((572, 596), R - 3, R + 3, BLUE, band((748, 776), R - 3, R + 3, BLUE))
    v["full_width_white"] = band(CASE_COLS, R - 3, R + 3, WHITE)
    v["corner_only_white"] = band((656, 684), R - 3, R + 3, WHITE)
    v["blue_core_green_edge"] = band(CASE_COLS, R - 3, R + 3, BLUE,
                                     band(CASE_COLS, R - 7, R + 7, GREEN))
    return v


def capture(exp=200000):
    from rig import bench as vm
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_plane_geom")
    run.mkdir(parents=True)
    V = variants()
    lock, sync = vm.open_rig()
    shots = {}
    try:
        sync.camera.set_exposure_us(exp)
        shots["black"] = sync.shoot(np.zeros((H, W, 3), np.uint8), raw=True).astype(np.float32)
        for k, fr in V.items():
            shots[k] = sync.shoot(fr, raw=True).astype(np.float32)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **{k: v.astype(np.float16) for k, v in shots.items()})
    return run


def analyse(run: Path, case_x=(470, 800)):
    z = np.load(run / "raw.npz")
    b = z["black"].astype(np.float32)
    keys = [k for k in z.files if k != "black"]
    D = {k: np.clip(z[k].astype(np.float32) - b, 0, None) for k in keys}
    yc = int(np.argmax(cv2.GaussianBlur(D["clean_windows"], (0, 0), 3).sum(axis=1)))
    bandr = slice(max(0, yc - 30), yc + 30)
    x0, x1 = case_x
    ref = None
    rep = {"band_rows_camera": [bandr.start, bandr.stop], "case_x": case_x, "variants": {}}
    for k in keys:
        p = cv2.GaussianBlur(D[k], (0, 0), 2)[bandr].sum(axis=0)[x0:x1]
        lvl = np.median(np.sort(p)[len(p) // 2:]) or 1.0
        cov = float((p > 0.25 * lvl).mean())
        even = float(np.median(p) / max(np.percentile(p, 90), 1e-9))
        mean = float(p.mean())
        rep["variants"][k] = {"coverage": round(cov, 3), "evenness": round(even, 3), "mean_glow": mean}
    ref = rep["variants"]["clean_windows"]["mean_glow"] or 1.0
    for k in keys:
        rep["variants"][k]["mean_rel"] = round(rep["variants"][k]["mean_glow"] / ref, 2)
        del rep["variants"][k]["mean_glow"]
    top = np.percentile(D["full_width"], 99.9) or 1.0
    tiles = []
    for k in keys:
        a = D[k][max(0, yc - 150):yc + 150, 380:940]
        a = (np.clip(a / top, 0, 1) ** 0.6 * 255).astype(np.uint8)
        a = cv2.resize(a, (400, 214))
        m = rep["variants"][k]
        cv2.putText(a, k, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)
        cv2.putText(a, f"cov {m['coverage']:.2f} even {m['evenness']:.2f} x{m['mean_rel']}", (5, 208),
                    cv2.FONT_HERSHEY_PLAIN, 0.9, 255, 1)
        tiles.append(a)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(run / "montage.png"), np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]))
    (run / "plane_geom.json").write_text(json.dumps(rep, indent=1))
    for k, m in sorted(rep["variants"].items(), key=lambda kv: -kv[1]["coverage"] * kv[1]["evenness"]):
        print(f"{k:22s} coverage {m['coverage']:.2f} evenness {m['evenness']:.2f} glow x{m['mean_rel']}")
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyse", type=Path)
    a = ap.parse_args()
    analyse(a.analyse if a.analyse else capture())
