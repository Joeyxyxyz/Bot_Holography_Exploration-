"""
Build the string-art shapes for a fitted case and simulate them from three viewpoints.

  python -m vol2.run_rods --case-json case_fit_tank_v3.json [--fill glycerin] [--tag v3]
Output: vol2/out/rods_<fill>_<tag>/<shape>_hdmi.png, <shape>_views.png (all light) and report.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from . import simulate
from .geometry import Case, load_case_json
from .render import Plane, joint_box
from .rods import render_shape
from .run import N_LIQ, save_views

OUT = Path(__file__).parent / "out"


def build(case_json, fill="glycerin", tag="", beam_mm=1.0):
    over, _ = load_case_json(case_json)
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
    out = OUT / (f"rods_{fill}" + (f"_{tag}" if tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    planes = {f: Plane(case, f) for f in ("A", "B")}
    centre, side, _, _ = joint_box(case, planes)
    size = 0.8 * side
    y_lo, y_hi = case.y_top + 6, case.y_base - 6
    rep = {"joint_box_side_mm": side, "size_mm": size, "y_range": [y_lo, y_hi], "shapes": {}}
    shapes = {"box3": ("box", 3), "box5": ("box", 5), "pyramid5": ("pyramid", 5),
              "diamond7": ("diamond", 7), "walls": ("walls", 0)}
    for name, (kind, n) in shapes.items():
        frame, r = render_shape(planes, kind, centre, size, y_lo, y_hi, n=max(n, 2))
        cv2.imwrite(str(out / f"{name}_hdmi.png"), frame)
        V = simulate.voxelise(case, simulate.lit_rays(case, frame), beam_mm=beam_mm)
        for deg in (60.0, 0.0):
            save_views(out / f"{name}_views_cam{int(deg)}.png", simulate.views(case, V, view_deg=deg))
        rep["shapes"][name] = {"layers": len(r["layers"]), "on_fraction": r["on_fraction"],
                               "rods": sum(len(l["A"]) + len(l["B"]) for l in r["layers"])}
        print(name, rep["shapes"][name], flush=True)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-json", type=Path, required=True)
    ap.add_argument("--fill", default="glycerin", choices=list(N_LIQ))
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    print(build(a.case_json, a.fill, a.tag))
