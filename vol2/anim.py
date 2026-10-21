"""
Animated volumetric shapes from rod layers ("string art" with life).

Every layer = 2 plane-A rods + 2 plane-B rods at one height -> a rhombus frame whose 4 corners are real
crossings and which has no ghosts (only 2 x 2 rods share that height). A shape is a stack of layers
(y, size, centre offset); an animation is that stack as a function of time t in [0, 1).
Layers ~3 mm apart keep rods of different layers from meeting (they are separated in height by more than
the ~1 mm beam everywhere along their length). Rods still run wall to wall: the shape is carried by the
crossings / ends, which is what reads by eye and on camera (A.6c).

  python -m vol2.anim --case-json case_fit_tank_v3.json [--frames 16] [--layers 13]
Writes vol2/out/anim_<tag>/<name>/fNN_hdmi.png (+ a 16-slot pattern-mode pack per animation) and still shapes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from . import flashpack
from .geometry import Case, load_case_json
from .render import H, W, Plane, draw, joint_box
from .rods import family_axes, layer_mirrors
from .run import N_LIQ

OUT = Path(__file__).parent / "out"


def render_layers(planes, axes, centre, layers, wc=3, wr=5):
    """layers: list of (y, size, offset_vec3). Returns the HDMI frame and the rods used."""
    f = np.zeros((H, W), np.uint8)
    used = []
    for y, s, off in layers:
        sel = layer_mirrors(planes, centre + off, y, s, s, axes)
        for fam in ("A", "B"):
            if sel[fam]:
                cs, rs = zip(*sel[fam])
                draw(f, cs, rs, wc, wr)
        used.append(sel)
    return f, used


# ---------------------------------------------------------------- shapes: (k / (n-1) in [0, 1], t) -> size factor, offset
def still_shapes():
    return {
        "sphere": lambda u: np.sqrt(max(0.0, 1 - (2 * u - 1) ** 2)),
        "hourglass": lambda u: 0.25 + 0.75 * abs(2 * u - 1),
        "cage": lambda u: 1.0,
        "pyramid": lambda u: u,                      # apex at the top (u = 0 is the top layer)
        "cone_down": lambda u: 1 - u,
    }


def animations():
    tau = 2 * np.pi
    return {
        # whole diamond grows and shrinks
        "breathing_diamond": lambda u, t: ((1 - abs(2 * u - 1)) * (0.55 + 0.45 * np.sin(tau * t)), 0.0, 0.0),
        # a bulge travelling upward through the stack
        "rising_wave": lambda u, t: (0.35 + 0.65 * (0.5 + 0.5 * np.cos(tau * (u + t))), 0.0, 0.0),
        # fixed-size frames whose centres orbit with a height-dependent phase -> a rotating twisted tower
        "twisting_tower": lambda u, t: (0.45, np.cos(tau * (t + 0.5 * u)), np.sin(tau * (t + 0.5 * u))),
        # box -> pyramid -> diamond -> box
        "morph": lambda u, t: (_morph(u, t), 0.0, 0.0),
        # a single frame bouncing up and down the column, with a fading trail
        "bounce": None,
    }


def _morph(u, t):
    box, pyr, dia = 1.0, u, 1 - abs(2 * u - 1)
    p = (t * 3) % 3
    a, b = [(box, pyr), (pyr, dia), (dia, box)][int(p)]
    w = p - int(p)
    w = 0.5 - 0.5 * np.cos(np.pi * w)                # ease
    return a * (1 - w) + b * w


def build(case_json, fill="glycerin", tag="v3", n_frames=16, n_layers=13, where="joint", size_mm=None):
    """where = "joint": largest jointly reachable square (toward the back corner, where the beams have faded);
    where = "middle": the centre of the liquid (Joey: beams fade about the centre -> float things there)."""
    over, _ = load_case_json(case_json)
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
    planes = {f: Plane(case, f) for f in ("A", "B")}
    axes = family_axes(planes)
    centre, side, _, _ = joint_box(case, planes)
    _, uA, uB = case.axes()
    if where == "middle":
        from .geometry import liquid_frame
        centre, _, _ = liquid_frame(case)
        side = size_mm / 0.8 if size_mm else 10.0
    elif where.startswith("qab:"):                      # explicit plan position "qab:<qa>,<qb>" (mm from the corner)
        qa, qb = (float(v) for v in where[4:].split(","))
        C, _, _ = case.axes()
        centre = C + qa * uA + qb * uB
        centre[1] = (case.y_base + case.y_top) / 2
        side = size_mm / 0.8 if size_mm else 10.0
    size_max = 0.8 * side
    orbit = 0.18 * side
    ys = np.linspace(case.y_top + 5, case.y_base - 5, n_layers)
    out = OUT / f"anim_{fill}_{tag}"
    out.mkdir(parents=True, exist_ok=True)
    rep = {"joint_box_side_mm": side, "size_max_mm": size_max, "orbit_mm": orbit,
           "layer_y_mm": ys.round(2).tolist(), "layer_spacing_mm": float(ys[1] - ys[0]), "stills": {}, "anims": {}}
    zero = np.zeros(3)
    for name, fn in still_shapes().items():
        layers = [(y, size_max * fn(k / (n_layers - 1)), zero) for k, y in enumerate(ys) if fn(k / (n_layers - 1)) > 0.02]
        f, _ = render_layers(planes, axes, centre, layers)
        cv2.imwrite(str(out / f"still_{name}_hdmi.png"), f)
        rep["stills"][name] = {"layers": len(layers), "on_fraction": float((f > 0).mean())}
    for name, fn in animations().items():
        d = out / name
        d.mkdir(exist_ok=True)
        frames = []
        for i in range(n_frames):
            t = i / n_frames
            if name == "bounce":
                pos = 0.5 - 0.5 * np.cos(2 * np.pi * t)          # 0 -> 1 -> 0 over the loop
                kk = pos * (n_layers - 1)
                layers = []
                for k, y in enumerate(ys):
                    dist = abs(k - kk)
                    if dist < 2.5:
                        layers.append((y, size_max * max(0.3, 1 - dist / 2.5), zero))
            else:
                layers = []
                for k, y in enumerate(ys):
                    s, ca, cb = fn(k / (n_layers - 1), t)
                    if s > 0.02:
                        layers.append((y, size_max * s, orbit * (ca * uA + cb * uB)))
            f, _ = render_layers(planes, axes, centre, layers)
            cv2.imwrite(str(d / f"f{i:02d}_hdmi.png"), f)
            frames.append(f)
        if n_frames == 16:
            flashpack.write_pack(d / "flash_pack", frames, [f"{name}_t{i:02d}" for i in range(16)],
                                 exposure_us=40000, note=f"{name}: 16 x 40 ms = 0.64 s loop")
        rep["anims"][name] = {"frames": n_frames, "dir": str(d)}
        print(name, "done", flush=True)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-json", type=Path, required=True)
    ap.add_argument("--fill", default="glycerin", choices=list(N_LIQ))
    ap.add_argument("--tag", default="v3")
    ap.add_argument("--frames", type=int, default=16)
    ap.add_argument("--layers", type=int, default=13)
    ap.add_argument("--where", default="joint", help='"joint", "middle" or "qab:<qa>,<qb>" in mm')
    ap.add_argument("--size-mm", type=float, default=None)
    a = ap.parse_args()
    print(build(a.case_json, a.fill, a.tag, a.frames, a.layers, a.where, a.size_mm))
