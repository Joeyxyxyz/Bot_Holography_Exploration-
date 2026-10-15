"""
What the lit volume looks like: every ON mirror (in plane A or B) is traced into the liquid with ALL its
legs (direct + after total internal reflection at the walls / surface) and accumulated as line density on
a 0.5 mm voxel grid. A scattering / fluorescent fill glows in proportion to the light passing through each
voxel (single scattering, no attenuation). The stock lens makes each mirror's beam `beam_mm` wide
(review: 0.5-1.8 mm depending on focus), modelled as an isotropic Gaussian blur of the line density.
[HEURISTIC]

Contrast (review-corrected): median over targets of the peak density near each target, divided by the
median density along lit beams at least `far_mm` from every target (a single beam, or a beam plus ghosts).
A 2x crossing gives ~2 at best. A single camera view gets no depth cue from it: the crossing is only brighter
where you look along it, so judge views, not this number alone.
Views are orthographic sum-projections: 'camera' (rotated view_deg about y), 'top', 'projector'.
"""
from __future__ import annotations

import numpy as np

from .geometry import Case, Rays, trace

VOX = 0.5


def lit_rays(case: Case, frame):
    """Trace every ON mirror inside plane A / plane B (all legs)."""
    rays = []
    for f, (c0, c1) in (("A", case.planeA_cols), ("B", case.planeB_cols)):
        rr, cc = np.nonzero(frame[:, c0:c1 + 1])
        if len(rr):
            rays.append(_trace_pairs(case, f, cc + c0, rr))
    return rays


def _trace_pairs(case, f, cols, rows):
    """trace() works on a col x row grid; trace the bounding grid once and keep the ON pairs."""
    G = trace(case, f, np.unique(cols), np.unique(rows))
    on = set(zip(cols.tolist(), rows.tolist()))
    keep = np.array([(int(c), int(r)) in on for c, r in zip(G.cols, G.rows)], bool)
    return Rays(f, G.cols[keep], G.rows[keep], G.p0[keep], G.d[keep], G.L[keep],
                G.mirror[keep], G.leg[keep], G.end[keep])


def voxelise(case: Case, rays, step=0.25, beam_mm=1.0, legs="all"):
    C, uA, uB = case.axes()
    lo, hi = case.t, case.S - case.t
    na = int(np.ceil((hi - lo) / VOX))
    ny = int(np.ceil(case.fill_mm / VOX))
    V = np.zeros((ny, na, na), np.float32)          # (y, qb, qa)
    for R in rays:
        sel = np.ones(len(R.L), bool) if legs == "all" else (R.leg == 0)
        p0s, ds, Ls = R.p0[sel], R.d[sel], R.L[sel]
        for s in range(0, len(Ls), 2000):
            p0, d, L = p0s[s:s + 2000], ds[s:s + 2000], Ls[s:s + 2000]
            n = int(np.ceil(L.max() / step)) + 1
            tau = np.linspace(0, 1, n)[None, :] * L[:, None]
            P = p0[:, None, :] + tau[..., None] * d[:, None, :]
            qa = ((P - C) @ uA - lo) / VOX
            qb = ((P - C) @ uB - lo) / VOX
            qy = (P[..., 1] - case.y_top) / VOX
            w = (L / (n - 1))[:, None] * np.ones_like(tau)
            ia, ib, iy = qa.astype(int).ravel(), qb.astype(int).ravel(), qy.astype(int).ravel()
            ok = (ia >= 0) & (ia < na) & (ib >= 0) & (ib < na) & (iy >= 0) & (iy < ny)
            np.add.at(V, (iy[ok], ib[ok], ia[ok]), w.ravel()[ok])
    return blur(V, beam_mm)


def blur(V, beam_mm):
    """Separable Gaussian with FWHM = beam_mm (per axis)."""
    sig = beam_mm / 2.355 / VOX
    if sig < 0.3:
        return V
    r = int(np.ceil(3 * sig))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    k /= k.sum()
    for ax in range(3):
        V = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), ax, V)
    return V.astype(np.float32)


def voxel_centres(case: Case, V):
    C, uA, uB = case.axes()
    ny, nb, na = V.shape
    iy, ib, ia = np.meshgrid(np.arange(ny), np.arange(nb), np.arange(na), indexing="ij")
    qa = case.t + (ia + 0.5) * VOX
    qb = case.t + (ib + 0.5) * VOX
    y = case.y_top + (iy + 0.5) * VOX
    X = C[None, None, None, :] + qa[..., None] * uA + qb[..., None] * uB
    X[..., 1] = y
    return X


def views(case: Case, V, view_deg=60.0):
    X = voxel_centres(case, V).reshape(-1, 3)
    w = V.ravel()
    m = w > 1e-6
    X, w = X[m], w[m]
    out = {}
    a = np.radians(view_deg)
    axes = {"camera": (np.array([np.cos(a), 0, -np.sin(a)]), np.array([0, 1.0, 0])),
            "top": (np.array([1.0, 0, 0]), np.array([0, 0, 1.0])),
            "projector": (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))}
    for k, (h, v) in axes.items():
        u, t = X @ h, X @ v
        if len(u) == 0:
            out[k] = np.zeros((10, 10), np.float32)
            continue
        u0, t0 = u.min(), t.min()
        img = np.zeros((int((t.max() - t0) / VOX) + 1, int((u.max() - u0) / VOX) + 1), np.float32)
        np.add.at(img, (((t - t0) / VOX).astype(int), ((u - u0) / VOX).astype(int)), w)
        out[k] = img
    return out


def view_dir(case: Case, V, az_deg, el_deg):
    """Orthographic sum view from a camera at azimuth az_deg around the case (0 = projector side, + toward the
    camera side) and elevation el_deg above the horizontal (90 = straight down). y is down in the world."""
    X = voxel_centres(case, V).reshape(-1, 3)
    w = V.ravel()
    m = w > 1e-6
    X, w = X[m], w[m]
    a, e = np.radians(az_deg), np.radians(el_deg)
    v = np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])     # camera -> case
    h = np.array([np.cos(a), 0.0, -np.sin(a)])                                 # image right
    up = np.cross(h, v)
    up /= np.linalg.norm(up)
    u, t = X @ h, X @ up
    if len(u) == 0:
        return np.zeros((10, 10), np.float32)
    u0, t0 = u.min(), t.min()
    img = np.zeros((int((t.max() - t0) / VOX) + 1, int((u.max() - u0) / VOX) + 1), np.float32)
    np.add.at(img, (((t - t0) / VOX).astype(int), ((u - u0) / VOX).astype(int)), w)
    return img


def _index(case: Case, V, pts):
    C, uA, uB = case.axes()
    ia = ((pts - C) @ uA - case.t) / VOX
    ib = ((pts - C) @ uB - case.t) / VOX
    iy = (pts[:, 1] - case.y_top) / VOX
    return iy, ib, ia


def contrast(case: Case, V, target_pts, near_mm=1.0, far_mm=4.0):
    """Peak near targets vs density along lit beams far from targets (see module doc)."""
    iy, ib, ia = _index(case, V, target_pts)
    k = int(np.ceil(near_mm / VOX))
    peaks = []
    for y, b, a in zip(iy.astype(int), ib.astype(int), ia.astype(int)):
        sl = V[max(0, y - k):y + k + 1, max(0, b - k):b + k + 1, max(0, a - k):a + k + 1]
        if sl.size:
            peaks.append(float(sl.max()))
    # distance of every voxel to the nearest target (coarse: via a dilated mask)
    far = np.ones(V.shape, bool)
    kf = int(np.ceil(far_mm / VOX))
    for y, b, a in zip(iy.astype(int), ib.astype(int), ia.astype(int)):
        far[max(0, y - kf):y + kf + 1, max(0, b - kf):b + kf + 1, max(0, a - kf):a + kf + 1] = False
    thr = 0.2 * float(np.percentile(V[V > 0], 99)) if (V > 0).any() else 0.0
    beam = V[far & (V > thr)]
    peak = float(np.median(peaks)) if peaks else 0.0
    bg = float(np.median(beam)) if beam.size else 0.0
    return {"target_peak_median": peak, "far_beam_median": bg,
            "contrast": (peak / bg) if bg > 0 else None,
            "lit_voxel_fraction": float((V > thr).mean())}
