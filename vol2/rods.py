"""
"String art" shapes: the lit rays ARE the shape.

In the glycerin every lit ray glows along its whole path, and the two families are near-horizontal fans. So the
lines we can draw cleanly are rods: one plane-A mirror block = one rod in the A direction at one height, likewise B.
A layer is a frame of 2 A rods + 2 B rods at the same height: their 4 crossings are the frame's corners, and with
only 2 x 2 rods per height there are no ghost crossings at that height (n^2 = 4 = the 4 corners).
Stacking layers gives the shape. The rods run wall to wall (a linear medium cannot stop a ray), so each layer reads
as a "#" whose inner rhombus is the shape's cross-section; the rhombus angle is the family crossing angle (~30 deg).
Shapes: box (equal layers), pyramid (shrinking to an apex crossing), diamond (grow then shrink), walls (dense layers
-> the 4 side faces as glowing sheets).
[HEURISTIC design; geometry from the fitted Case, uncalibrated beyond the column fit.]
"""
from __future__ import annotations

import numpy as np

from .geometry import Case
from .render import H, W, Plane, draw


def family_axes(planes: dict):
    """Median in-plan direction of each family's direct legs, and its in-plan perpendicular."""
    out = {}
    for f in ("A", "B"):
        d = np.median(planes[f].direct.d, axis=0)
        d = np.array([d[0], 0.0, d[2]])
        d /= np.linalg.norm(d)
        out[f] = (d, np.array([-d[2], 0.0, d[0]]))
    return out


def layer_mirrors(planes: dict, centre, y, size_a, size_b, axes=None, tol_mm=0.8):
    """Mirrors for one frame at height y: A rods offset +/- size_a/2 across the A direction, B rods +/- size_b/2
    across the B direction. size 0 -> a single rod through the centre (an apex). Returns {family: [(col, row)]}."""
    axes = axes or family_axes(planes)
    sel = {}
    for f, size in (("A", size_a), ("B", size_b)):
        _, perp = axes[f]
        offs = [0.0] if size <= 0 else [-size / 2, size / 2]
        pts = np.array([centre + o * perp for o in offs])
        pts[:, 1] = y
        c, r, d, ok = planes[f].nearest(pts)
        sel[f] = [(int(cc), int(rr)) for cc, rr, dd, k in zip(c, r, d, ok) if k and dd <= tol_mm]
    return sel


def shape_layers(kind, centre, size, y_lo, y_hi, n=5):
    """(y, size) per layer. y increases downward (world y is down)."""
    ys = np.linspace(y_lo, y_hi, n)
    if kind == "box":
        return [(y, size) for y in ys]
    if kind == "pyramid":                  # apex at the top (smallest y), base at the bottom
        return [(y, size * (k / (n - 1))) for k, y in enumerate(ys)]
    if kind == "diamond":
        mid = (n - 1) / 2
        return [(y, size * (1 - abs(k - mid) / mid)) for k, y in enumerate(ys)]
    if kind == "walls":
        ys = np.arange(y_lo, y_hi + 1e-9, 0.6)
        return [(y, size) for y in ys]
    raise ValueError(kind)


def render_shape(planes: dict, kind, centre, size, y_lo, y_hi, n=5, wc=3, wr=5):
    axes = family_axes(planes)
    frame = np.zeros((H, W), np.uint8)
    rep = {"kind": kind, "layers": []}
    for y, s in shape_layers(kind, centre, size, y_lo, y_hi, n):
        sel = layer_mirrors(planes, centre, y, s, s, axes)
        for f in ("A", "B"):
            if sel[f]:
                cs, rs = zip(*sel[f])
                draw(frame, cs, rs, wc, wr)
        rep["layers"].append({"y": round(float(y), 2), "size": round(float(s), 2),
                              "A": sel["A"], "B": sel["B"]})
    rep["on_fraction"] = float((frame > 0).mean())
    return frame, rep
