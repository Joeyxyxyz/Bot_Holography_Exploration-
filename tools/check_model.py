"""Quick offline checks of the TIR-aware ray model (no hardware). Run: python tools/check_model.py"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from vol2.geometry import Case, crossing_angle_deg, pixel_dirs, trace_plane
from vol2.render import Plane, joint_box, pair, cube_points

for liq, n in (("water", 1.333), ("glycerin", 1.47)):
    for bw in ("tir", "absorb"):
        c = Case(n_liq=n, back_walls=bw)
        C, uA, uB = c.axes()
        assert np.allclose(C, [0, 0, c.D]) and np.allclose(pixel_dirs(c, c.col_corner, c.row_ref), [0, 0, 1])
        A = trace_plane(c, "A")
        d = A.leg == 0
        ends = {k: round(float(np.mean(A.end[d] == k)), 3) for k in ("tir", "wall", "absorbed", "base", "surface", "tir_lost")}
        print(f"{liq:8s} back_walls={bw:6s} mirrors {d.sum():5d} legs {len(A.L):5d} "
              f"max_leg {int(A.leg.max())} direct-leg ends {ends} y_base {c.y_base:.2f}")
    c = Case(n_liq=n)
    P = {f: Plane(c, f) for f in "AB"}
    print("  crossing (direct legs, plane median)", round(crossing_angle_deg(P["A"].rays, P["B"].rays), 2))
    centre, side, both, q = joint_box(c, P)
    print("  joint box side", side, "mm at qa/qb centre", None if centre is None else np.round(((centre - C) @ uA, (centre - C) @ uB), 1))
    X = cube_points(c, side, 0.0, centre=centre)[0]
    R = pair(P, X)
    ok = R["ok"]
    print("  cube pairs placed", int(ok.sum()), "/", len(X), " crossing err median/p95",
          np.round(np.median(R["err"][ok]), 3), np.round(np.percentile(R["err"][ok], 95), 3))
# pitch sensitivity: base height and joint box with a 5 deg pitched projector (placeholder)
c = Case(pitch_deg=5.0)
print("pitch 5: corner", np.round(c.axes()[0], 1), "y_base", round(c.y_base, 2))
