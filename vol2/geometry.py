"""
Two-plane volumetric projection: ray model of the case (tank_v1, corner-on).

World frame (mm): projector pinhole at the origin, y DOWN (vertical), x to the right as seen from the
projector, z away from it. The case stands upright in this frame.

Projector (pinhole): a DMD pixel (c, r) has camera-frame direction ((c - c0) / fx, (r - r0) / fy, 1),
fx = cpm * D, fy = rpm * D (cols / rows per mm at distance D). The projector axis is pitched down by
pitch_deg (rotation about x), then yawed so the ray of the corner pixel (col_corner, row_ref) has x = 0.
The case's outer corner sits on that ray at distance D. With c0 = col_corner, r0 = row_ref and
pitch 0 (the defaults) this is the original model: corner ray = +z.
  The LightCrafter 4500 has a 100 % vertical throw offset (DLPU011E Table 1-1), so the true principal point is
  near row 1140 and the corner ray is generally NOT horizontal; c0 / r0 / pitch are placeholders until they
  are fitted on the filled case (review 2026-09-29). [HEURISTIC]

Case: square in plan, outer side S, wall t, rotated psi about y (psi = 0: corner-on, faces at 45 deg).
  uA = face A direction from the corner (back-left), uB = face B direction (back-right).
  Face A (toward the camera, DMD cols < corner) lies along uA, inward normal uB; face B along uB, inward normal uA.
Rays refract air -> acrylic -> liquid at the entry face (vector Snell). Inside the liquid each mirror's light
is a list of LEGS: at a side wall, if n_liq * sin(i) > 1 the light crosses into the acrylic but is totally
reflected at the outer acrylic/air face, and comes back walked off by 2 t tan(theta_acr) (review finding: ~2/3
of each family does this at the back walls, 55-57 deg in water). back_walls="absorb" models black tape / paint
in optical contact with the outside of the two back walls (it frustrates the TIR and absorbs). The liquid
surface reflects totally at grazing incidence (no walk-off); the black base absorbs.
Each mirror is modelled as its chief ray; the stock lens makes the real beam 0.5-1.8 mm wide depending on
focus (review). [HEURISTIC]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Case:
    D: float = 406.0              # pinhole -> outer corner along the corner ray (Joey: ~16 in; pupil unknown)
    col_corner: float = 642.0     # DMD column of the corner ray (middle of the edge band 628-656)
    row_ref: float = 820.0        # DMD row of the corner ray's reference point
    cpm: float = 2.49             # DMD cols per mm at D. UPPER cell-boundary fit to call-outs 544 / 740;
                                  # call-outs allow ~1.8-2.49, dot checks ~2.40-2.49 (review). [HEURISTIC]
    rpm: float = 5.3              # DMD rows per mm at D: unfitted placeholder (~2 x cpm). [HEURISTIC]
    psi_deg: float = 0.0          # case rotation about y; 0 = corner-on
    c0: Optional[float] = None    # principal point column (None -> col_corner)
    r0: Optional[float] = None    # principal point row (None -> row_ref; TI 100 % offset -> ~1140)
    pitch_deg: float = 0.0        # projector axis pitched down (+) about x
    S: float = 61.6               # outer side (mean of 63.1 bottom / 60.1 top: taper ignored)
    t: float = 1.5                # wall thickness [HEURISTIC]
    r_corner: float = 8.0         # entries closer than this to the corner (along the face) are dropped;
                                  # 8 mm = the dark edge band cols 628-656; the rounding itself is ~3 mm
    n_acr: float = 1.49
    n_liq: float = 1.333          # water; glycerin 1.47
    row_base: float = 1016.0      # DMD row where the base top meets the corner (call-out: row I/J boundary)
    fill_mm: float = 60.0         # liquid height above the base top
    back_walls: str = "tir"       # "tir" (bare acrylic) | "absorb" (black tape in optical contact outside)
    max_bounces: int = 3
    planeA_cols: tuple = (540, 641)   # wide: trace() keeps only mirrors that enter face A validly
    planeB_cols: tuple = (643, 744)
    rows: tuple = (624, 1016)

    @property
    def y_base(self) -> float:
        """World y of the base top at the corner: the (col_corner, row_base) ray at the corner's depth."""
        C, _, _ = self.axes()
        d = pixel_dirs(self, self.col_corner, self.row_base)
        return float(d[1] / d[2] * C[2])

    @property
    def y_top(self) -> float:     # liquid surface (y is down)
        return self.y_base - self.fill_mm

    def _R(self):
        """camera frame -> world: pitch about x, then yaw about y so the corner ray has x = 0."""
        p = np.radians(self.pitch_deg)
        Rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
        v = _cam_dir(self, np.array([self.col_corner]), np.array([self.row_ref]))[0]
        w = Rx @ v
        yaw = -np.arctan2(w[0], w[2])
        Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
        return Ry @ Rx

    def axes(self):
        q = np.radians(self.psi_deg)
        R = np.array([[np.cos(q), 0, np.sin(q)], [0, 1, 0], [-np.sin(q), 0, np.cos(q)]])
        uA = R @ np.array([-1.0, 0.0, 1.0]) / np.sqrt(2)
        uB = R @ np.array([1.0, 0.0, 1.0]) / np.sqrt(2)
        wc = self._R() @ _cam_dir(self, np.array([self.col_corner]), np.array([self.row_ref]))[0]
        C = self.D * wc
        return C, uA, uB


def _cam_dir(case: Case, c, r):
    c0 = case.col_corner if case.c0 is None else case.c0
    r0 = case.row_ref if case.r0 is None else case.r0
    c = np.atleast_1d(np.asarray(c, float))
    r = np.atleast_1d(np.asarray(r, float))
    d = np.stack([(c - c0) / (case.cpm * case.D), (r - r0) / (case.rpm * case.D), np.ones_like(c)], -1)
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def pixel_dirs(case: Case, c, r):
    """World unit directions of DMD pixels (c, r)."""
    d = _cam_dir(case, c, r) @ case._R().T
    return d[0] if np.ndim(c) == 0 and np.ndim(r) == 0 else d


def refract(d, n, eta):
    """Vector Snell. d: (...,3) unit incident; n: (3,) unit normal pointing AGAINST d; eta = n1/n2.
    Returns (t, ok) with ok False on total internal reflection."""
    cosi = -(d @ n)
    k = 1.0 - eta ** 2 * (1.0 - cosi ** 2)
    ok = k >= 0
    t = eta * d + (eta * cosi - np.sqrt(np.clip(k, 0, None)))[..., None] * n
    return t / np.linalg.norm(t, axis=-1, keepdims=True), ok


@dataclass
class Rays:
    """One entry per LEG. mirror indexes the unique (col, row) mirror; leg 0 is the direct leg."""
    family: str
    cols: np.ndarray
    rows: np.ndarray
    p0: np.ndarray                # (N,3) leg start in the liquid
    d: np.ndarray                 # (N,3) unit direction
    L: np.ndarray                 # (N,) leg length (mm)
    mirror: np.ndarray = None     # (N,) mirror index
    leg: np.ndarray = None        # (N,) 0 = direct, 1.. = after total internal reflection
    end: np.ndarray = None        # (N,) how the leg ended: 'wall', 'tir', 'absorbed', 'base', 'surface'
    meta: dict = field(default_factory=dict)

    def direct(self) -> "Rays":
        m = self.leg == 0
        return Rays(self.family, self.cols[m], self.rows[m], self.p0[m], self.d[m], self.L[m],
                    self.mirror[m], self.leg[m], self.end[m], dict(self.meta))


def _walls(case: Case):
    """Inner side walls as (normal pointing INTO the liquid, offset, name, is_back)."""
    C, uA, uB = case.axes()
    lo, hi = case.t, case.S - case.t
    return C, [(uA, lo, "qa_lo", False), (-uA, -hi, "qa_hi", True),
               (uB, lo, "qb_lo", False), (-uB, -hi, "qb_hi", True)]


def trace(case: Case, family: str, cols, rows) -> Rays:
    """Trace a col x row grid of one plane. Mirrors whose ray does not enter that plane's face inside the
    liquid (misses, corner band, base, above the fill, or past the far edge) are dropped."""
    C, uA, uB = case.axes()
    cc, rr = np.meshgrid(np.asarray(cols, float), np.asarray(rows, float))
    cc, rr = cc.ravel(), rr.ravel()
    d = pixel_dirs(case, cc, rr).reshape(-1, 3)
    along, inward = (uA, uB) if family == "A" else (uB, uA)
    s = (C @ inward) / (d @ inward)
    P = s[:, None] * d
    a = (P - C) @ along
    ok = (s > 0) & (a > case.r_corner) & (a < case.S - case.t)
    d1, ok1 = refract(d, -inward, 1.0 / case.n_acr)
    s1 = case.t / (d1 @ inward)
    P1 = P + s1[:, None] * d1
    a1 = (P1 - C) @ along
    d2, ok2 = refract(d1, -inward, case.n_acr / case.n_liq)
    y_base, y_top = case.y_base, case.y_top
    ok &= ok1 & ok2 & (a1 > case.t) & (a1 < case.S - case.t) & (P1[:, 1] <= y_base) & (P1[:, 1] >= y_top)
    cc, rr, p, v = cc[ok], rr[ok], P1[ok], d2[ok]
    mid = np.arange(len(cc))
    _, walls = _walls(case)
    legs = []
    active = np.ones(len(cc), bool)
    for bounce in range(case.max_bounces + 1):
        idx = np.nonzero(active)[0]
        if len(idx) == 0:
            break
        pp, vv = p[idx], v[idx]
        cand, kinds = [], []
        with np.errstate(divide="ignore", invalid="ignore"):
            for n_in, off, name, _ in walls:
                # plane (X - C) . n_in = off; the leg leaves the liquid where it decreases through off
                dn = vv @ n_in
                sc = (off - (pp - C) @ n_in) / dn
                cand.append(np.where((sc > 1e-6) & (dn < 0), sc, np.inf))
                kinds.append(name)
            for yb, name in ((y_base, "base"), (y_top, "surface")):
                sc = (yb - pp[:, 1]) / vv[:, 1]
                cand.append(np.where(sc > 1e-6, sc, np.inf))
                kinds.append(name)
        cand = np.stack(cand)
        k = np.argmin(cand, axis=0)
        Lk = cand[k, np.arange(len(idx))]
        good = np.isfinite(Lk)
        end = np.full(len(idx), "wall", dtype=object)
        nxt_p, nxt_v, cont = pp.copy(), vv.copy(), np.zeros(len(idx), bool)
        hit = pp + np.where(good, Lk, 0)[:, None] * vv
        for j, name in enumerate(kinds):
            sel = good & (k == j)
            if not sel.any():
                continue
            if name == "base":
                end[sel] = "base"
                continue
            if name == "surface":
                n_in = np.array([0.0, 1.0, 0.0])        # into the liquid (down)
                cosi = np.abs(vv[sel] @ n_in)
                tir = case.n_liq * np.sqrt(1 - cosi ** 2) > 1.0
                s_idx = np.nonzero(sel)[0]
                end[s_idx] = np.where(tir, "tir", "surface")
                r_idx = s_idx[tir]
                nxt_v[r_idx] = vv[r_idx] - 2 * (vv[r_idx] @ n_in)[:, None] * n_in
                nxt_p[r_idx] = hit[r_idx]
                cont[r_idx] = True
                continue
            n_in, _, _, is_back = walls[j]
            s_idx = np.nonzero(sel)[0]
            if is_back and case.back_walls == "absorb":
                end[s_idx] = "absorbed"
                continue
            cosi = np.abs(vv[s_idx] @ n_in)
            sini = np.sqrt(np.clip(1 - cosi ** 2, 0, 1))
            tir = case.n_liq * sini > 1.0
            end[s_idx] = np.where(tir, "tir", "wall")
            r_idx = s_idx[tir]
            if len(r_idx):
                refl = vv[r_idx] - 2 * (vv[r_idx] @ n_in)[:, None] * n_in
                tang = vv[r_idx] - (vv[r_idx] @ n_in)[:, None] * n_in
                tang /= np.linalg.norm(tang, axis=1, keepdims=True)
                s_acr = case.n_liq * sini[tir] / case.n_acr
                walk = 2 * case.t * s_acr / np.sqrt(1 - s_acr ** 2)
                start = hit[r_idx] + walk[:, None] * tang
                inside = in_liquid(case, start + 1e-6 * refl)
                end_sel = r_idx[~inside]
                end[end_sel] = "tir_lost"
                keep = r_idx[inside]
                nxt_v[keep] = refl[inside]
                nxt_p[keep] = start[inside]
                cont[keep] = True
        gi = idx[good]
        legs.append((gi, pp[good], vv[good], Lk[good], np.full(good.sum(), bounce), end[good]))
        # prepare the next bounce
        new_active = np.zeros(len(cc), bool)
        new_active[idx[cont]] = True
        p[idx[cont]], v[idx[cont]] = nxt_p[cont], nxt_v[cont]
        active = new_active
    if not legs:
        z = np.zeros((0, 3))
        return Rays(family, np.array([]), np.array([]), z, z, np.array([]), np.array([], int),
                    np.array([], int), np.array([], object))
    gi = np.concatenate([x[0] for x in legs])
    return Rays(family, cc[gi], rr[gi], np.concatenate([x[1] for x in legs]),
                np.concatenate([x[2] for x in legs]), np.concatenate([x[3] for x in legs]),
                mid[gi], np.concatenate([x[4] for x in legs]), np.concatenate([x[5] for x in legs]),
                meta={"n_liq": case.n_liq, "psi_deg": case.psi_deg, "back_walls": case.back_walls})


def trace_plane(case: Case, family: str, step_c=1, step_r=1) -> Rays:
    c0, c1 = case.planeA_cols if family == "A" else case.planeB_cols
    return trace(case, family, np.arange(c0, c1 + 1, step_c), np.arange(case.rows[0], case.rows[1] + 1, step_r))


def crossing_angle_deg(ra: Rays, rb: Rays) -> float:
    """Angle between the median in-plan directions of the two families' DIRECT legs (x-z plane)."""
    a = np.median(ra.d[ra.leg == 0][:, [0, 2]], axis=0)
    b = np.median(rb.d[rb.leg == 0][:, [0, 2]], axis=0)
    cosang = a @ b / np.linalg.norm(a) / np.linalg.norm(b)
    return float(np.degrees(np.arccos(np.clip(cosang, -1, 1))))


def in_liquid(case: Case, X):
    C, uA, uB = case.axes()
    X = np.atleast_2d(X)
    qa, qb = (X - C) @ uA, (X - C) @ uB
    lo, hi = case.t, case.S - case.t
    return (qa > lo) & (qa < hi) & (qb > lo) & (qb < hi) & (X[:, 1] < case.y_base) & (X[:, 1] > case.y_top)


def liquid_frame(case: Case):
    """Centre of the liquid and its in-plan axes (for placing content)."""
    C, uA, uB = case.axes()
    centre = C + (case.S / 2) * (uA + uB)
    centre = centre.copy()
    centre[1] = (case.y_base + case.y_top) / 2
    return centre, uA, uB
