"""
Build the two-plane content set offline (no hardware):

  python -m vol2.run [--fill water|glycerin] [--back-walls tir|absorb] [--beam-mm 1.0]

For each piece of content: the HDMI frame (1140x912, invert off), the render report (how close each
target point is to a real ray), a simulated volume (camera / top / projector views) and the target
contrast. Plus a 16-frame rotating-cube sequence as HDMI frames and as a one-image pattern-mode pack
(with its plane check and procedure.txt; files only, the GUI steps are Joey's).
Output: vol2/out/<fill>_<back_walls>/...  (placement is uncalibrated until vol2.calib_sweep has run)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from . import flashpack, simulate
from .geometry import Case, crossing_angle_deg
from .render import Plane, coverage, cube_points, helix_points, joint_box, lattice_points, render

OUT = Path(__file__).parent / "out"
N_LIQ = {"water": 1.333, "glycerin": 1.47}


def save_views(path, vw):
    tiles = []
    for k in ("camera", "top", "projector"):
        a = vw[k]
        a = np.clip(a / max(np.percentile(a[a > 0], 99.5) if (a > 0).any() else 1, 1e-9), 0, 1) ** 0.5
        a = (a * 255).astype(np.uint8)
        a = cv2.resize(a, (int(a.shape[1] * 300 / max(a.shape)), int(a.shape[0] * 300 / max(a.shape))),
                       interpolation=cv2.INTER_AREA)
        t = np.zeros((320, 320), np.uint8)
        t[:a.shape[0], :a.shape[1]] = a
        cv2.putText(t, k, (4, 316), cv2.FONT_HERSHEY_PLAIN, 1.0, 255, 1)
        tiles.append(t)
    cv2.imwrite(str(path), np.hstack(tiles))


def build(fill="water", back_walls="tir", beam_mm=1.0, case_json=None, tag=""):
    over = json.loads(Path(case_json).read_text(encoding="utf-8-sig")) if case_json else {}
    over = {k: (tuple(v) if isinstance(v, list) else v) for k, v in over.items()}
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": back_walls, **over})
    out = OUT / (f"{fill}_{back_walls}" + (f"_{tag}" if tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    planes = {f: Plane(case, f) for f in ("A", "B")}
    rep = {"case": {k: (list(v) if isinstance(v, tuple) else v) for k, v in case.__dict__.items()},
           "mirrors_traced": {f: int(len(p.direct.L)) for f, p in planes.items()},
           "legs_traced": {f: int(len(p.rays.L)) for f, p in planes.items()},
           "beam_mm": beam_mm,
           "crossing_angle_deg": crossing_angle_deg(planes["A"].rays, planes["B"].rays),
           "content": {}}
    print("crossing angle", round(rep["crossing_angle_deg"], 2), "mirrors", rep["mirrors_traced"],
          "legs", rep["legs_traced"], flush=True)
    centre, side, both, q = joint_box(case, planes)
    rep["joint_box"] = {"centre_mm": centre.tolist(), "side_mm": float(side),
                        "joint_plan_area_mm2_all_heights": float(both.sum() * (q[1] - q[0]) ** 2)}
    m, _ = coverage(case, planes)
    lut = np.array([[0, 0, 0], [255, 140, 0], [0, 140, 255], [255, 255, 255]], np.uint8)  # BGR: A blue, B orange
    cov = cv2.resize(lut[m], (360, 360), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(out / "coverage_plan_mid.png"), cov)
    print("joint box", rep["joint_box"], flush=True)
    s0 = float(side)                       # cube fits the box at yaw 0
    s45 = float(side) / np.sqrt(2)         # fits at any yaw (for the rotation)
    r_hx = float(side) / 2 - 1.5           # helix radius inside the joint box
    content = {
        # ghost-free (one point per height): the main demo
        "helix": (helix_points(case, centre, r_hx), "cross"),
        # shared heights -> n^2 crossings / horizontal planes light up: kept to show the limitation
        "lattice5": (lattice_points(case, both, q, 5.0), "cross"),
        f"cube{s0:.0f}_yaw0": (cube_points(case, s0, 0.0, centre=centre)[0], "cross"),
        f"cube{s45:.0f}_yaw45": (cube_points(case, s45, 45.0, centre=centre)[0], "cross"),
        f"cube{s0:.0f}_yaw0_onlyA": (cube_points(case, s0, 0.0, centre=centre)[0], "A"),
    }
    for name, (X, mode) in content.items():
        frame, r = render(planes, X, mode, beam_mm=beam_mm)
        cv2.imwrite(str(out / f"{name}_hdmi.png"), frame)
        V = simulate.voxelise(case, simulate.lit_rays(case, frame), beam_mm=beam_mm)
        save_views(out / f"{name}_views.png", simulate.views(case, V))
        r["volume"] = simulate.contrast(case, V, X)
        rep["content"][name] = r
        print(name, json.dumps({k: r.get(k) for k in ("placed", "dropped", "crossing_err_mm", "on_fraction",
                                                        "volume")}), flush=True)
    # rotating helix: 16 frames over one turn (ghost-free in every frame).
    # 16 = G0-G7 + R0-R7 exactly, so a GUI G/R plane swap only rotates the loop (flashpack docstring)
    frames, names = [], []
    for k in range(16):
        ph = k * 360.0 / 16
        f, _ = render(planes, helix_points(case, centre, r_hx, phase_deg=ph), "cross")
        frames.append(f)
        names.append(f"helix_ph{ph:05.1f}")
    anim = out / "anim_helix_rotate"
    anim.mkdir(exist_ok=True)
    for old in anim.glob("*_hdmi.png"):                # drop frames of an older, longer sequence
        old.unlink()
    for f, n in zip(frames, names):
        cv2.imwrite(str(anim / f"{n}_hdmi.png"), f)
    rep["flash_pack"] = flashpack.write_pack(out / "flash_helix_rotate", frames, names, exposure_us=20000,
                                            note="16 x 20 ms = 0.32 s per turn")
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fill", default="water", choices=list(N_LIQ))
    ap.add_argument("--back-walls", default="tir", choices=["tir", "absorb"])
    ap.add_argument("--beam-mm", type=float, default=1.0)
    ap.add_argument("--case-json", type=Path, help="Case field overrides (e.g. a calib_sweep fit)")
    ap.add_argument("--tag", default="", help="suffix for the output folder")
    a = ap.parse_args()
    build(a.fill, a.back_walls, a.beam_mm, a.case_json, a.tag)
