"""
Calibrate the case pose from the filled (fluorescent) case: the review's #1 requirement before trusting placement.

Capture (takes the rig lock; HDMI video mode; colour via raw BGR frames, no LED change):
  python -m vol2.calib_sweep capture [--color blue] [--exp 66667]
    column sweep : a 2-mirror-wide vertical line at every 2nd column 500..790, rows 624..1016
    row sweep    : a 3-mirror-tall horizontal line at every 4th row 580..1076, in plane A (cols 560-610)
                   and in plane B (cols 670-720) separately
    + black frames between blocks (background)
Analyse (offline):
  python -m vol2.calib_sweep analyse <run_dir> [--roi x0 y0 x1 y1]
    per-line glow energy inside the camera ROI (the case), edge columns / rows at half maximum,
    then fit (col_corner, cpm, psi) to the three column edges (face-A silhouette, corner, face-B silhouette)
    and report the fitted Case parameters and residuals. [PROVED as arithmetic; the edges are measured.]
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
BGR = {"blue": (1, 0, 0), "green": (0, 1, 0), "red": (0, 0, 1), "white": (1, 1, 1)}


SWEEP = {"cols": (500, 790), "col_rows": (624, 1017), "planeA": (560, 611), "planeB": (670, 721),
         "rows": (580, 1076)}                      # tank_v1 defaults; override with --map case_map_*.json


def sweep_from_map(path):
    """Sweep ranges from a case map with 'planes' (A / B dmd_cols) and a case row range."""
    import json as _j
    m = _j.loads(Path(path).read_text(encoding="utf-8-sig"))
    a, b = m["planes"]["A"]["dmd_cols"], m["planes"]["B"]["dmd_cols"]
    r0, r1 = m.get("case_dmd_rows", [624, 1017])
    pad = 40
    return {"cols": (max(0, a[0] - pad), min(W - 2, b[1] + pad)), "col_rows": (r0, r1),
            "planeA": (a[0] + 8, a[1] - 8), "planeB": (b[0] + 8, b[1] - 8),
            "rows": (max(0, r0 - pad), min(H - 3, r1 + pad))}


def sweep_frames(sw=None):
    sw = sw or SWEEP
    out = [("black_0", np.zeros((H, W), np.uint8))]
    for c in range(sw["cols"][0], sw["cols"][1] + 1, 2):
        f = np.zeros((H, W), np.uint8)
        f[sw["col_rows"][0]:sw["col_rows"][1], c:c + 2] = 255
        out.append((f"col_{c}", f))
    out.append(("black_1", np.zeros((H, W), np.uint8)))
    for plane, (c0, c1) in (("A", sw["planeA"]), ("B", sw["planeB"])):
        for r in range(sw["rows"][0], sw["rows"][1] + 1, 4):
            f = np.zeros((H, W), np.uint8)
            f[r:r + 3, c0:c1] = 255
            out.append((f"row{plane}_{r}", f))
    out.append(("black_2", np.zeros((H, W), np.uint8)))
    return out


def capture(color="blue", exp=66667, case_map=None):
    from rig import bench as vm
    sw = sweep_from_map(case_map) if case_map else SWEEP
    frames = sweep_frames(sw)
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + f"_calib_{color}")
    run.mkdir(parents=True)
    vm.DUTY = 1.0
    lock, sync = vm.open_rig()
    shots = {}
    try:
        sync.camera.set_exposure_us(exp)
        b, g, r = BGR[color]
        for name, f in frames:
            img = sync.shoot(np.dstack([f * b, f * g, f * r]).astype(np.uint8), raw=True)
            shots[name] = img.astype(np.float16)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **shots)
    cv2.imwrite(str(run / "black.png"), np.clip(shots["black_0"].astype(np.float32), 0, 255).astype(np.uint8))
    (run / "meta.json").write_text(json.dumps({"color": color, "exposure_us": exp, "n": len(frames),
                                               "sweep": sw, "case_map": str(case_map) if case_map else None,
                                               "note": "intensity through the stock lens, incoherent"}, indent=1))
    print(run)
    return run


def _edges(x, e):
    """Rising and falling half-maximum crossings of a profile (linear interpolation)."""
    e = np.asarray(e, float)
    e = e - np.percentile(e, 5)
    half = 0.5 * e.max()
    above = e >= half
    out = []
    for i in range(1, len(e)):
        if above[i] != above[i - 1]:
            t = (half - e[i - 1]) / (e[i] - e[i - 1])
            out.append(("rise" if above[i] else "fall", float(x[i - 1] + t * (x[i] - x[i - 1]))))
    return out


def analyse(run: Path, roi=None):
    z = np.load(run / "raw.npz")
    black = np.mean([z[k].astype(np.float32) for k in z.files if k.startswith("black")], axis=0)
    if roi is None:            # auto: pixels that any column line lights well above background
        acc = np.max([np.clip(z[k].astype(np.float32) - black, 0, None) for k in z.files if k.startswith("col_")], axis=0)
        m = acc > np.percentile(acc, 99) * 0.3
        ys, xs = np.nonzero(m)
        roi = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else (0, 0, 1440, 1080)
    x0, y0, x1, y1 = roi
    prof = {}
    for kind in ("col_", "rowA_", "rowB_"):
        keys = sorted((k for k in z.files if k.startswith(kind)), key=lambda k: int(k.split("_")[1]))
        xs = np.array([int(k.split("_")[1]) for k in keys])
        e = np.array([np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1].sum() for k in keys])
        prof[kind.rstrip("_")] = {"x": xs.tolist(), "energy": e.tolist(), "edges": _edges(xs, e)}
    rep = {"roi": roi, "profiles": {k: {"edges": v["edges"]} for k, v in prof.items()}}
    # strip plot for eyeballing
    img = np.zeros((300, 3 * 300), np.uint8)
    for i, (k, v) in enumerate(prof.items()):
        e = np.asarray(v["energy"]); e = e / max(e.max(), 1e-9)
        pts = np.stack([np.linspace(i * 300 + 5, i * 300 + 295, len(e)), 290 - e * 280], 1).astype(np.int32)
        cv2.polylines(img, [pts], False, 255, 1)
        cv2.putText(img, k, (i * 300 + 8, 18), cv2.FONT_HERSHEY_PLAIN, 1.0, 255, 1)
    cv2.imwrite(str(run / "profiles.png"), img)
    col_edges = [p for _, p in prof["col"]["edges"]]
    if len(col_edges) >= 3:
        rep["fit"] = fit_columns(col_edges[0], (col_edges[1] + col_edges[2]) / 2 if len(col_edges) >= 4 else None,
                                 col_edges[-1])
    (run / "calib.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


def fit_columns(left, corner, right, D=406.0):
    """Grid-fit (col_corner, cpm, psi) so the model's face-A silhouette / corner / face-B silhouette columns match."""
    from vol2.geometry import Case, trace
    best = None
    corners = [corner] if corner is not None else list(np.arange(620, 665, 1.0))
    for cc in corners:
        for cpm in np.arange(2.0, 2.81, 0.02):
            for psi in np.arange(-12, 12.1, 1.0):
                c = Case(col_corner=float(cc), cpm=float(cpm), psi_deg=float(psi), D=D, r_corner=0.0)
                a = trace(c, "A", np.arange(480, int(cc)), np.array([c.row_ref]))
                b = trace(c, "B", np.arange(int(cc) + 1, 820), np.array([c.row_ref]))
                if len(a.cols) == 0 or len(b.cols) == 0:
                    continue
                res = np.hypot(a.cols[a.leg == 0].min() - left, b.cols[b.leg == 0].max() - right)
                if best is None or res < best[0]:
                    best = (float(res), float(cc), float(cpm), float(psi))
    return {"residual_cols": best[0], "col_corner": best[1], "cpm": best[2], "psi_deg": best[3], "D": D,
            "note": "silhouettes use the sharp outer corner (r_corner 0); rounding ~3 mm not modelled"} if best else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--color", default="blue", choices=list(BGR))
    c.add_argument("--exp", type=int, default=66667)
    c.add_argument("--map", type=Path, help="case_map_*.json with planes A/B (sweep ranges follow it)")
    a = sub.add_parser("analyse")
    a.add_argument("run", type=Path)
    a.add_argument("--roi", type=int, nargs=4)
    args = ap.parse_args()
    if args.cmd == "capture":
        capture(args.color, args.exp, args.map)
    else:
        analyse(args.run, args.roi)
