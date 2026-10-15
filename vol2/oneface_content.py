"""
Single-face content (case right side up, light into ONE flat face), inside the measured clean window
(runs/20261005T201957_oneface_edges: clean DMD cols 620-714, rows 732-939; content kept to cols 628-704,
rows 776-914 = grid 10-12 x G-I). Blue only, graded through the measured duty curve (volplay.load_duty_lut).
One face = every lit mirror is one ray straight into the liquid, so each shape is a 2D DMD pattern extruded
along the projection direction (no crossings, no ghosts).

  python -m vol2.oneface_content build  [scene ...]       # 12-16 sampled frames -> vol2/out/oneface/<scene>/f###.png
  python -m vol2.oneface_content play <scene> [--seconds 20] [--fps 60]   # rig lock, STOP ends it
scenes: of_plane, of_plane_sweep, of_ribbon, of_wave, of_pyramid, of_pyramid_build, of_stack_breathe, of_combo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vol2.volplay import load_duty_lut, duty_to_level, play  # noqa: E402

H, W = 1140, 912
C0, C1 = 628, 704          # content columns (inclusive)
R0, R1 = 776, 914          # content rows (inclusive)
CM = (C0 + C1) // 2        # 666
OUT = ROOT / "vol2" / "out" / "oneface"
PERIOD = {"of_plane": 1.0, "of_plane_sweep": 4.0, "of_ribbon": 4.0, "of_wave": 2.0, "of_pyramid": 1.0,
          "of_pyramid_build": 6.0, "of_stack_breathe": 4.0, "of_combo": 6.0,
          "of_plane6": 1.0, "of_plane24": 1.0, "of_plane40": 1.0, "of_diamond": 1.0, "of_sphere": 1.0, "of_block": 1.0,
          "of_sphere_pulse": 3.0, "of_ribbon_double": 4.0, "of_ocean": 6.0}


def band(d, r0, r1, c0, c1, v):
    r0, r1 = max(R0, int(r0)), min(R1, int(r1))
    c0, c1 = max(C0, int(c0)), min(C1, int(c1))
    if r1 >= r0 and c1 >= c0:
        d[r0:r1 + 1, c0:c1 + 1] = np.maximum(d[r0:r1 + 1, c0:c1 + 1], v)


def plane(d, rc, thick=12, v=1.0):
    band(d, rc - thick // 2, rc + thick // 2, C0, C1, v)


def ribbon(d, t, T=4.0):
    rows = np.arange(R0, R1 + 1)
    th = 2 * np.pi * ((rows - R0) / 140.0 - t / T)           # one full twist over the height, rotating
    hw = 34 * np.abs(np.cos(th)) + 2                            # projected half-width of a twisting strip
    cc = CM + 4 * np.sin(2 * np.pi * t / T)
    face = 0.45 + 0.55 * np.abs(np.sin(th))                     # edge-on -> brighter (more strip along the ray)
    for r, w, f in zip(rows, hw, face):
        lo, hi = int(round(cc - w)), int(round(cc + w))
        band(d, r, r, lo, hi, 0.5 * f)
        band(d, r, r, lo, lo + 2, 1.0)                          # bright ribbon edges
        band(d, r, r, hi - 2, hi, 1.0)


def wave(d, t, T=2.0):
    rows = np.arange(R0, R1 + 1)
    c = CM + 30 * np.sin(2 * np.pi * ((rows - R0) / 70.0 - t / T))
    for r, x in zip(rows, c):
        band(d, r, r, x - 1, x + 1, 1.0)


def pyramid(d, n_show=6, scale=1.0, base=None):
    # 6 stepped layers, base at the bottom of the window, 6 rows thick, 18-row pitch, widths 76 -> 16 cols
    base = R1 - 4 if base is None else base
    for k in range(min(n_show, 6)):
        hw = scale * (38 - 6 * k)
        rc = base - 22 * k
        duty = 0.55 + 0.09 * k                                  # top layers brighter (smaller, so they read)
        band(d, rc - 3, rc + 3, CM - hw, CM + hw, duty)


def scene(name, t):
    d = np.zeros((H, W), np.float32)
    if name == "of_plane":
        plane(d, 845, 12)
    elif name == "of_plane_sweep":
        plane(d, 845 + 58 * np.sin(2 * np.pi * t / 4.0), 12)
    elif name == "of_ribbon":
        ribbon(d, t)
    elif name == "of_wave":
        wave(d, t)
    elif name == "of_pyramid":
        pyramid(d)
    elif name == "of_pyramid_build":
        pyramid(d, n_show=1 + int((t % 6.0) / 6.0 * 7))
    elif name == "of_stack_breathe":
        pyramid(d, scale=0.55 + 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 4.0)))
    elif name == "of_combo":                                    # pyramid with a plane sweeping through it
        pyramid(d)
        plane(d, 845 + 60 * np.sin(2 * np.pi * t / 6.0), 4, 0.8)
    elif name.startswith("of_plane") and name[8:].isdigit():
        plane(d, 845, int(name[8:]))
    elif name == "of_diamond":                                  # layered diamond: widths grow then shrink
        for k in range(7):
            hw = 38 * (1 - abs(k - 3) / 3.5)
            band(d, R0 + 6 + 20 * k - 3, R0 + 6 + 20 * k + 3, CM - hw, CM + hw, 0.6 + 0.4 * (1 - abs(k - 3) / 3))
    elif name in ("of_sphere", "of_sphere_pulse"):              # disc stack, sphere-like profile (extruded: a cylinder)
        s = 1.0 if name == "of_sphere" else 0.6 + 0.4 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 3.0))
        Rr, rc = 66 * s, 845
        for y in np.arange(-Rr + 4, Rr - 3, 11):
            hw = 38 * s * np.sqrt(max(0.0, 1 - (y / Rr) ** 2))
            band(d, rc + y - 2, rc + y + 2, CM - hw, CM + hw, 0.55 + 0.45 * hw / 38)
    elif name == "of_block":                                    # solid filled block = the clean window itself
        band(d, R0, R1, C0, C1, 0.7)
    elif name == "of_ocean":                                    # height field: wavy row band per column = corrugated sheet
        for c in range(C0, C1 + 1):
            rc = 850 + 22 * np.sin(2 * np.pi * (c / 38.0 - t / 3.0)) + 9 * np.sin(2 * np.pi * (c / 17.0 + t / 2.0))
            band(d, rc - 3, rc + 3, c, c, 1.0)
            band(d, rc + 4, rc + 30, c, c, 0.12)                # faint body under the surface
    elif name == "of_ribbon_double":
        ribbon(d, t)
        d2 = np.zeros_like(d); ribbon(d2, t + 2.0); d[:] = np.maximum(d, 0.8 * d2)
    else:
        raise SystemExit(f"unknown scene {name}")
    return d


def to_bgr(d, lut):
    f = np.zeros((H, W, 3), np.uint8)
    f[..., 0] = duty_to_level(d, lut)
    return f


def build(names, n=12):
    lut = load_duty_lut()
    for name in names:
        out = OUT / name
        out.mkdir(parents=True, exist_ok=True)
        for p in out.glob("f*.png"):
            p.unlink()
        T = PERIOD[name]
        k = 1 if T <= 1.0 else n
        for i in range(k):
            f = to_bgr(scene(name, T * i / k), lut)
            assert not f[:, :C0].any() and not f[:, C1 + 1:].any() and not f[:R0].any() and not f[R1 + 1:].any()
            cv2.imwrite(str(out / f"f{i:03d}.png"), f)
        (out / "info.json").write_text(json.dumps({"scene": name, "period_s": T, "frames": k, "window": [C0, C1, R0, R1],
                                                   "duty_lut": lut[2]}, indent=1))
        print(out, k, flush=True)


def play_scene(name, seconds, fps):
    lut = load_duty_lut()
    T = PERIOD[name]
    n = max(1, int(round(T * fps)))
    frames = [to_bgr(scene(name, i / fps), lut) for i in range(n)]
    info = {"scene": name, "frames_per_cycle": n, "fps": fps}
    info["playback"] = play(frames, fps, seconds)
    print(json.dumps(info), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}_play.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("scenes", nargs="*", default=list(PERIOD))
    p = sub.add_parser("play"); p.add_argument("scene"); p.add_argument("--seconds", type=float, default=20.0)
    p.add_argument("--fps", type=float, default=60.0)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.scenes)
    else:
        play_scene(a.scene, a.seconds, a.fps)
