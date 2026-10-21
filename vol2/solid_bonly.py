"""
B-input / A-output solids (Joey: keep face A as the clean output window).

  mode "brefl": cross-section = band of DIRECT face-B rays x band of REFLECTED face-B rays (TIR at the back-right
                wall). True 3D crossing, every lit mirror is in face B. Dimmer (reflected legs travel further).
  mode "bband": band of direct face-B rays only. Seen through face A the shape's outline is crisp, but it is
                extruded along the B ray direction (a shaped beam), not localised in depth.
  python -m vol2.solid_bonly --case-json case_fit_tank_v4.json --size-mm 7 --height-mm 14
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .geometry import Case, load_case_json
from .oneface import one_face_planes
from .render import joint_box
from .rods import family_axes
from .run import N_LIQ
from .solid import PROFILES, render_solid

OUT = Path(__file__).parent / "out"


def build(case_json, size_mm=7.0, height_mm=14.0, fill="glycerin", n_frames=16):
    over, _ = load_case_json(case_json)
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
    planes, _ = one_face_planes(case, "B")
    axes = family_axes(planes)
    centre, side, both, q = joint_box(case, planes)
    C, uA, uB = case.axes()
    mid = (case.y_base + case.y_top) / 2
    centre = centre.copy()
    centre[1] = mid
    size = min(size_mm, 0.8 * side)
    rep = {"joint_box_side_mm": side, "size_mm": size,
           "centre_qab": [float((centre - C) @ uA), float((centre - C) @ uB)], "stills": {}}
    print(rep, flush=True)
    out = OUT / f"solid_bonly_{fill}"
    out.mkdir(parents=True, exist_ok=True)
    y_lo, y_hi = mid - height_mm / 2, mid + height_mm / 2
    for mode, fams in (("brefl", ("A", "B")), ("bband", ("A",))):
        for name, prof in PROFILES.items():
            f = render_solid(planes, axes, centre, prof, y_lo, y_hi, size, fams=fams)
            cols = np.nonzero(f.any(0))[0]
            cv2.imwrite(str(out / f"{mode}_{name}_hdmi.png"), f)
            rep["stills"][f"{mode}_{name}"] = {"on_px": int((f > 0).sum()),
                                               "cols": [int(cols.min()), int(cols.max())] if len(cols) else None}
        d = out / f"{mode}_bouncing_ball"
        d.mkdir(exist_ok=True)
        bh = 0.45 * height_mm
        lo, hi = case.y_top + 4, case.y_base - 4
        for i in range(n_frames):
            cy = lo + bh / 2 + (hi - lo - bh) * (0.5 - 0.5 * np.cos(2 * np.pi * i / n_frames))
            f = render_solid(planes, axes, centre, PROFILES["ball"], cy - bh / 2, cy + bh / 2, size, fams=fams)
            cv2.imwrite(str(d / f"f{i:02d}_hdmi.png"), f)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    for k, v in rep["stills"].items():
        print(k, v)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-json", type=Path, required=True)
    ap.add_argument("--size-mm", type=float, default=7.0)
    ap.add_argument("--height-mm", type=float, default=14.0)
    a = ap.parse_args()
    print(build(a.case_json, a.size_mm, a.height_mm))
