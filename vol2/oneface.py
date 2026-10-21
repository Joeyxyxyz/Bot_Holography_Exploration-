"""
One input face, two ray families (Joey: "a & b plane configurations could go into face B and show out on A").

Light entering face B hits the back-right wall beyond the critical angle (~61 deg in glycerin) and is totally
reflected back into the liquid (geometry.trace legs). So face B alone supplies two families inside the case:
  family "direct"    = leg 0 of each face-B mirror
  family "reflected" = leg 1 of each face-B mirror (after TIR, with the ~3 mm walk-off)
They cross at ~58 deg instead of the ~30 deg between faces A and B, and face A carries no entry light,
so it is a clean output window for the camera / eye. The same rod-layer shapes are built by treating the
two families as the two "planes" (render.pair / rods.layer_mirrors work on any objects with .direct legs).
Requires bare acrylic on the back-right wall (tape there would absorb the reflected family).
[HEURISTIC model: walk-off, wall flatness and the TIR leg geometry are not yet measured.]

  python -m vol2.oneface --case-json case_fit_tank_v3.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from . import simulate
from .geometry import Case, Rays, crossing_angle_deg
from .render import Plane, coverage, joint_box
from .rods import family_axes, layer_mirrors
from .anim import still_shapes, render_layers
from .run import N_LIQ, save_views

OUT = Path(__file__).parent / "out"


class LegPlane(Plane):
    """A Plane over a chosen subset of legs (no tracing of its own)."""

    def __init__(self, case: Case, family: str, legs: Rays):
        self.case, self.family = case, family
        self.rays = legs
        self.direct = legs


def legs_subset(R: Rays, sel) -> Rays:
    return Rays(R.family, R.cols[sel], R.rows[sel], R.p0[sel], R.d[sel], R.L[sel],
                R.mirror[sel], R.leg[sel], R.end[sel], dict(R.meta))


def one_face_planes(case: Case, face="B"):
    full = Plane(case, face)
    R = full.rays
    direct = legs_subset(R, R.leg == 0)
    refl = legs_subset(R, R.leg == 1)
    return {"A": LegPlane(case, "direct", direct), "B": LegPlane(case, "reflected", refl)}, full


def build(case_json, fill="glycerin", tag="v3", n_layers=13):
    over = json.loads(Path(case_json).read_text(encoding="utf-8-sig"))
    over = {k: (tuple(v) if isinstance(v, list) else v) for k, v in over.items()}
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
    planes, full = one_face_planes(case, "B")
    out = OUT / f"oneface_{fill}_{tag}"
    out.mkdir(parents=True, exist_ok=True)
    ang = crossing_angle_deg(planes["A"].direct, Rays("x", planes["B"].direct.cols, planes["B"].direct.rows,
                                                      planes["B"].direct.p0, planes["B"].direct.d,
                                                      planes["B"].direct.L, planes["B"].direct.mirror,
                                                      np.zeros_like(planes["B"].direct.leg),
                                                      planes["B"].direct.end))
    centre, side, both, q = joint_box(case, planes)
    m, _ = coverage(case, planes)
    lut = np.array([[0, 0, 0], [255, 140, 0], [0, 140, 255], [255, 255, 255]], np.uint8)
    cv2.imwrite(str(out / "coverage_plan_mid.png"), cv2.resize(lut[m], (360, 360), interpolation=cv2.INTER_NEAREST))
    rep = {"crossing_angle_deg": ang, "direct_legs": int(len(planes["A"].direct.L)),
           "reflected_legs": int(len(planes["B"].direct.L)), "joint_box_side_mm": side,
           "joint_plan_area_mm2": float(both.sum() * (q[1] - q[0]) ** 2), "stills": {}}
    print(json.dumps({k: rep[k] for k in ("crossing_angle_deg", "direct_legs", "reflected_legs",
                                          "joint_box_side_mm", "joint_plan_area_mm2")}), flush=True)
    if centre is None or side < 3:
        (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
        return out
    axes = family_axes(planes)
    smax = 0.8 * side
    ys = np.linspace(case.y_top + 5, case.y_base - 5, n_layers)
    zero = np.zeros(3)
    for name, fn in still_shapes().items():
        layers = [(y, smax * fn(k / (n_layers - 1)), zero) for k, y in enumerate(ys) if fn(k / (n_layers - 1)) > 0.02]
        f, _ = render_layers(planes, axes, centre, layers)
        cv2.imwrite(str(out / f"still_{name}_hdmi.png"), f)
        V = simulate.voxelise(case, simulate.lit_rays(case, f), beam_mm=1.0)
        save_views(out / f"still_{name}_views.png", simulate.views(case, V))
        rep["stills"][name] = {"on_fraction": float((f > 0).mean()),
                               "cols": [int(np.nonzero(f.any(0))[0].min()), int(np.nonzero(f.any(0))[0].max())]
                               if f.any() else None}
        print(name, rep["stills"][name], flush=True)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-json", type=Path, required=True)
    ap.add_argument("--fill", default="glycerin", choices=list(N_LIQ))
    ap.add_argument("--tag", default="v3")
    a = ap.parse_args()
    print(build(a.case_json, a.fill, a.tag))
