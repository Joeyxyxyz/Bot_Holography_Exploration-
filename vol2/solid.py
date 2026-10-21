"""
Solid volumetric shapes (Joey: "project a solid shape").

At each height the shape's cross-section is the overlap of a filled band of plane-A rays and a filled band of
plane-B rays (each band = every mirror whose ray passes within +/- s/2 of the centre line). Two contiguous bands
cross in exactly one rhombus, so the cross-section glows at ~2x and the rest of each band at 1x; there are no
ghost crossings. Layers every ~1 mm make the solid continuous in height. Cross-sections are rhombi set by the two
ray families (~30 deg apart in plan), so "cube" = rhombic prism, "ball" = rhombic bicone-like solid with a
spherical size profile. Placed off the rounded corner (case_fit_tank_v4: A <= 645, B >= 695) at qa = qb = 40 mm.
[HEURISTIC geometry; uncalibrated beyond the column fit.]

  python -m vol2.solid --case-json case_fit_tank_v4.json --where qab:40,40 --size-mm 7
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .geometry import Case, load_case_json
from .render import H, W, Plane, draw
from .rods import family_axes
from .run import N_LIQ

OUT = Path(__file__).parent / "out"


def band_mirrors(plane, centre, perp, y, size, step=0.3, tol_mm=0.8):
    offs = np.arange(-size / 2, size / 2 + 1e-9, step) if size > 0 else np.array([0.0])
    pts = centre[None, :] + offs[:, None] * perp[None, :]
    pts[:, 1] = y
    c, r, d, ok = plane.nearest(pts)
    keep = ok & (d <= tol_mm)
    return set(zip(c[keep].tolist(), r[keep].tolist()))


def render_solid(planes, axes, centre, profile, y_lo, y_hi, size_max, dy=1.0, offset=None, fams=("A", "B")):
    """profile(u) -> size factor in [0, 1], u = 0 at the top layer (y_lo), 1 at the bottom (y_hi).
    fams: which families to light ("A","B" = the two faces; with one-face planes "A" = direct B legs and
    "B" = reflected B legs, all from face-B mirrors)."""
    f = np.zeros((H, W), np.uint8)
    ys = np.arange(y_lo, y_hi + 1e-9, dy)
    n = max(len(ys) - 1, 1)
    for k, y in enumerate(ys):
        s = size_max * profile(k / n)
        if s <= 0.05:
            continue
        c0 = centre + (offset(k / n) if offset else 0.0)
        for fam in fams:
            sel = band_mirrors(planes[fam], c0, axes[fam][1], y, s)
            if sel:
                cs, rs = zip(*sel)
                draw(f, cs, rs, 3, 5)
    return f


PROFILES = {
    "cube": lambda u: 1.0,
    "ball": lambda u: np.sqrt(max(0.0, 1 - (2 * u - 1) ** 2)),
    "pyramid": lambda u: u,
    "diamond": lambda u: 1 - abs(2 * u - 1),
    "cone_down": lambda u: 1 - u,
}


def build(case_json, where="qab:40,40", size_mm=7.0, fill="glycerin", tag="solid", height_mm=None, n_frames=16):
    over, _ = load_case_json(case_json)
    case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
    planes = {f: Plane(case, f) for f in ("A", "B")}
    axes = family_axes(planes)
    C, uA, uB = case.axes()
    qa, qb = (float(v) for v in where[4:].split(","))
    centre = C + qa * uA + qb * uB
    mid = (case.y_base + case.y_top) / 2
    centre[1] = mid
    h = height_mm or size_mm * 1.6                        # rhombic cross-sections look small: give them height
    y_lo, y_hi = mid - h / 2, mid + h / 2
    out = OUT / f"{tag}_{fill}"
    out.mkdir(parents=True, exist_ok=True)
    rep = {"centre_qab": [qa, qb], "size_mm": size_mm, "height_mm": h, "stills": {}}
    for name, prof in PROFILES.items():
        f = render_solid(planes, axes, centre, prof, y_lo, y_hi, size_mm)
        cv2.imwrite(str(out / f"solid_{name}_hdmi.png"), f)
        rep["stills"][name] = {"on_px": int((f > 0).sum())}
        print(name, rep["stills"][name], flush=True)
    # bouncing solid ball: a ball of ~0.45 h travelling the full liquid height and back
    travel_lo, travel_hi = case.y_top + 4, case.y_base - 4
    d = out / "anim_bouncing_ball"
    d.mkdir(exist_ok=True)
    bh = 0.45 * h
    for i in range(n_frames):
        t = i / n_frames
        cy = travel_lo + bh / 2 + (travel_hi - travel_lo - bh) * (0.5 - 0.5 * np.cos(2 * np.pi * t))
        f = render_solid(planes, axes, centre, PROFILES["ball"], cy - bh / 2, cy + bh / 2, size_mm)
        cv2.imwrite(str(d / f"f{i:02d}_hdmi.png"), f)
    # pulsing solid diamond
    d = out / "anim_pulsing_diamond"
    d.mkdir(exist_ok=True)
    for i in range(n_frames):
        k = 0.6 + 0.4 * np.sin(2 * np.pi * i / n_frames)
        f = render_solid(planes, axes, centre, PROFILES["diamond"], mid - k * h / 2, mid + k * h / 2, size_mm * k)
        cv2.imwrite(str(d / f"f{i:02d}_hdmi.png"), f)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-json", type=Path, required=True)
    ap.add_argument("--where", default="qab:40,40")
    ap.add_argument("--size-mm", type=float, default=7.0)
    ap.add_argument("--height-mm", type=float, default=None)
    ap.add_argument("--tag", default="solid")
    a = ap.parse_args()
    print(build(a.case_json, a.where, a.size_mm, tag=a.tag, height_mm=a.height_mm))
