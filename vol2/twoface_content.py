"""
Two-face content, case right side up and corner-on (re-map runs/20261005T204658_twoface_map):
face A clean DMD cols 576-648, corner fold 652-670 (dark), face B clean 674-710, liquid rows ~724-976.
Every element is designed in DMD space: an A column and a B column at the same rows give a crossing (2x glow)
inside the liquid; one A + one B per height = no ghosts.
  python -m vol2.twoface_content build [scene ...]
  python -m vol2.twoface_content play <scene> [--seconds 20]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import cv2, numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from vol2.volplay import load_duty_lut, duty_to_level, play  # noqa: E402
H, W = 1140, 912
A_WIN, B_WIN, R_WIN = (600, 648), (674, 708), (760, 950)
OUT = ROOT / "vol2" / "out" / "twoface"
PERIOD = {"tf_woven_box": 1.0, "tf_woven_A": 1.0, "tf_woven_B": 1.0, "tf_cube_edges": 1.0, "tf_depth_sweep": 6.0,
          "tf_helix": 4.0, "tf_double_helix": 4.0, "tf_box_level_sweep": 4.0, "tf_orbit_box": 6.0}

def put(d, c, r0, r1, v=1.0, wc=3):
    """one sheet piece: column c (wc wide) over rows r0..r1, clipped to its face window"""
    win = A_WIN if c < 660 else B_WIN
    c = int(round(c))
    if not (win[0] <= c <= win[1]): return
    r0, r1 = max(R_WIN[0], int(r0)), min(R_WIN[1], int(r1))
    if r1 < r0: return
    d[r0:r1 + 1, c - wc // 2:c + wc // 2 + 1] = np.maximum(d[r0:r1 + 1, c - wc // 2:c + wc // 2 + 1], v)

A1, A2, B1, B2 = 626, 640, 682, 696          # woven box columns
LEVELS = (790, 850, 910)

def woven(d, a=(A1, A2), b=(B1, B2), levels=LEVELS, th=5, fams="AB", v=1.0):
    for r in levels:
        for c in (a if "A" in fams else ()) + (b if "B" in fams else ()):
            put(d, c, r - th // 2, r + th // 2, v)

def scene(name, t):
    d = np.zeros((H, W), np.float32)
    if name == "tf_woven_box":
        woven(d)
    elif name == "tf_woven_A":
        woven(d, fams="A")
    elif name == "tf_woven_B":
        woven(d, fams="B")
    elif name == "tf_cube_edges":                # 4 sheets (2A x 2B) -> 4 vertical crossing edges, '#' rims top/bottom
        for c in (A1, A2, B1, B2):
            put(d, c, 790, 910, 0.45)
        woven(d, levels=(790, 910), th=3)
    elif name == "tf_depth_sweep":               # a crossing post moving from the corner into the depth and back
        k = 22 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 6.0))
        put(d, 646 - k, 800, 900); put(d, 676 + k, 800, 900)
    elif name in ("tf_helix", "tf_double_helix"):
        strands = 1 if name == "tf_helix" else 2
        blk = 6
        for i, r in enumerate(range(R_WIN[0] + 20, R_WIN[1] - 20, blk)):
            s = i % strands
            th = 2 * np.pi * ((r - R_WIN[0]) / 150.0 + t / 4.0) + s * np.pi
            put(d, 633 + 11 * np.cos(th), r, r + blk - 3)
            put(d, 690 + 11 * np.sin(th), r, r + blk - 3)
    elif name == "tf_box_level_sweep":            # woven box with a 4th level sweeping up and down through it
        woven(d, levels=(790, 910), v=0.8)
        woven(d, levels=(int(850 + 55 * np.sin(2 * np.pi * t / 4.0)),))
    elif name == "tf_orbit_box":                  # the rhombus of 4 crossings orbits in plan (columns move in a circle)
        th = 2 * np.pi * t / 6.0
        da, db = 8 * np.cos(th), 8 * np.sin(th)
        woven(d, a=(A1 + da, A2 + da), b=(B1 + db, B2 + db))
    else:
        raise SystemExit(name)
    return d

def to_bgr(d, lut):
    f = np.zeros((H, W, 3), np.uint8); f[..., 0] = duty_to_level(d, lut); return f

def build(names, n=12):
    lut = load_duty_lut()
    for name in names:
        out = OUT / name; out.mkdir(parents=True, exist_ok=True)
        for p in out.glob("f*.png"): p.unlink()
        T = PERIOD[name]; k = 1 if T <= 1.0 else n
        for i in range(k):
            cv2.imwrite(str(out / f"f{i:03d}.png"), to_bgr(scene(name, T * i / k), lut))
        print(out, k, flush=True)

def play_scene(name, seconds, fps=60.0):
    lut = load_duty_lut(); T = PERIOD[name]; n = max(1, int(round(T * fps)))
    frames = [to_bgr(scene(name, i / fps), lut) for i in range(n)]
    info = {"scene": name, "frames_per_cycle": n, "fps": fps, "playback": play(frames, fps, seconds)}
    print(json.dumps(info), flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("scenes", nargs="*", default=list(PERIOD))
    p = sub.add_parser("play"); p.add_argument("scene"); p.add_argument("--seconds", type=float, default=20.0)
    a = ap.parse_args()
    build(a.scenes) if a.cmd == "build" else play_scene(a.scene, a.seconds)
