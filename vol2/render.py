"""
3D content -> DMD frames for the two-plane volume.

Inversion uses DIRECT legs only (light after a total internal reflection is a side effect, not an address).
For a target point X in cross mode, the plane-A and plane-B mirrors are chosen as a PAIR: among the k nearest
direct legs of each family, the pair whose closest-approach midpoint is nearest X (review: picking each family
independently hides the real crossing error). The report gives |crossing - X|, the A-B gap, and the crossing's
depth elongation ~ w / sin(theta / 2) for beam width w.
Modes:
  cross : points reached by BOTH families light their A and B mirrors -> the point sits on a crossing
  A / B : one family only (a segment along that family's ray direction collapses to a single rod)
Incoherent light adds: a crossing is ~2x the brightness of either beam alone. [ASSERTED]
"""
from __future__ import annotations

import numpy as np

from .geometry import Case, Rays, liquid_frame, trace_plane

H, W = 1140, 912


class Plane:
    def __init__(self, case: Case, family: str):
        self.case, self.family = case, family
        self.rays: Rays = trace_plane(case, family)          # all legs (for simulation)
        self.direct: Rays = self.rays.direct()               # addressing

    def nearest_k(self, X, k=1, chunk=128, y_pad=2.0):
        """(M,3) points -> indices (M,k) into self.direct and perpendicular distances (M,k); inf = none.
        Speed: points are processed in height order and each chunk only tests legs whose height range
        (over their length, +/- y_pad mm) overlaps the chunk's; a leg outside it is > y_pad from every point."""
        X = np.atleast_2d(X).astype(np.float64)
        R = self.direct
        idx = np.zeros((len(X), k), int)
        dist = np.full((len(X), k), np.inf)
        if len(R.L) == 0:
            return idx, dist
        y_end = R.p0[:, 1] + R.L * R.d[:, 1]
        ylo, yhi = np.minimum(R.p0[:, 1], y_end) - y_pad, np.maximum(R.p0[:, 1], y_end) + y_pad
        order = np.argsort(X[:, 1], kind="stable")
        for s in range(0, len(X), chunk):
            sel = order[s:s + chunk]
            x = X[sel]
            cand = np.nonzero((yhi >= x[:, 1].min()) & (ylo <= x[:, 1].max()))[0]
            if len(cand) == 0:
                continue
            v = x[:, None, :] - R.p0[cand][None, :, :]
            tau = np.einsum("mnk,nk->mn", v, R.d[cand])
            d2 = np.einsum("mnk,mnk->mn", v, v) - tau ** 2
            d2 = np.where((tau >= 0) & (tau <= R.L[cand][None, :]), d2, np.inf)
            kk = min(k, d2.shape[1])
            part = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
            pd = np.take_along_axis(d2, part, 1)
            o = np.argsort(pd, axis=1)
            idx[sel, :kk] = cand[np.take_along_axis(part, o, 1)]
            dist[sel, :kk] = np.sqrt(np.maximum(np.take_along_axis(pd, o, 1), 0))
        # a pad-limited search cannot see legs farther than y_pad: treat those distances as unknown
        dist[dist > y_pad] = np.inf
        return idx, dist

    def nearest(self, X):
        """(M,3) points -> (cols, rows, dist_mm, inside) of the closest direct leg per point."""
        i, d = self.nearest_k(X, 1)
        R = self.direct
        ok = np.isfinite(d[:, 0])
        return R.cols[i[:, 0]].astype(int), R.rows[i[:, 0]].astype(int), d[:, 0], ok


def _closest(pa, da, pb, db):
    """Closest approach of lines pa + s da and pb + u db (unit d). Returns midpoint, gap, s, u."""
    w0 = pa - pb
    b = np.sum(da * db, -1)
    dd, e = np.sum(da * w0, -1), np.sum(db * w0, -1)
    den = np.maximum(1 - b * b, 1e-12)
    s = (b * e - dd) / den
    u = (e - b * dd) / den
    qa, qb = pa + s[..., None] * da, pb + u[..., None] * db
    return (qa + qb) / 2, np.linalg.norm(qa - qb, axis=-1), s, u


def pair(planes: dict, X, k=6, tol_mm=0.6):
    """Joint A/B choice per point. Returns dict with cols/rows per family, crossing error, gap, ok."""
    A, B = planes["A"], planes["B"]
    ia, da = A.nearest_k(X, k)
    ib, db = B.nearest_k(X, k)
    RA, RB = A.direct, B.direct
    M = len(X)
    best_err = np.full(M, np.inf)
    best = np.zeros((M, 2), int)
    gap_best = np.full(M, np.inf)
    for p in range(k):
        for q in range(k):
            va = np.isfinite(da[:, p]) & (da[:, p] <= tol_mm)
            vb = np.isfinite(db[:, q]) & (db[:, q] <= tol_mm)
            m, gap, s, u = _closest(RA.p0[ia[:, p]], RA.d[ia[:, p]], RB.p0[ib[:, q]], RB.d[ib[:, q]])
            inside = (s >= 0) & (s <= RA.L[ia[:, p]]) & (u >= 0) & (u <= RB.L[ib[:, q]])
            err = np.where(va & vb & inside, np.linalg.norm(m - X, axis=1), np.inf)
            better = err < best_err
            best_err[better] = err[better]
            gap_best[better] = gap[better]
            best[better] = np.stack([ia[better, p], ib[better, q]], 1)
    ok = np.isfinite(best_err)
    return {"A": (RA.cols[best[:, 0]].astype(int), RA.rows[best[:, 0]].astype(int)),
            "B": (RB.cols[best[:, 1]].astype(int), RB.rows[best[:, 1]].astype(int)),
            "err": best_err, "gap": gap_best, "ok": ok}


def draw(frame, cols, rows, wc=3, wr=5):
    """Odd-sized block CENTRED on each (col, row) (review: even blocks shift the beam axis half a mirror)."""
    hc, hr = wc // 2, wr // 2
    for c, r in zip(np.asarray(cols, int), np.asarray(rows, int)):
        frame[max(0, r - hr):min(H, r + hr + 1), max(0, c - hc):min(W, c + hc + 1)] = 255
    return frame


def render(planes: dict, X, mode="cross", tol_mm=0.6, cross_tol_mm=1.0, wc=3, wr=5, beam_mm=1.0):
    """Returns (frame, report). Points that cannot be placed within tolerance are reported, not drawn."""
    frame = np.zeros((H, W), np.uint8)
    X = np.atleast_2d(X)
    rep = {"mode": mode, "n_points": int(len(X)), "block_mirrors": [wc, wr]}
    if mode == "cross":
        P = pair(planes, X, tol_mm=tol_mm)
        ok = P["ok"] & (P["err"] <= cross_tol_mm)
        for f in ("A", "B"):
            c, r = P[f]
            draw(frame, c[ok], r[ok], wc, wr)
            rep[f] = {"unique_pixels": int(len(set(zip(c[ok], r[ok]))))}
        e = P["err"][ok]
        rep["placed"] = int(ok.sum())
        rep["dropped"] = int((~ok).sum())
        rep["crossing_err_mm"] = {"median": float(np.median(e)), "p95": float(np.percentile(e, 95))} if ok.any() else None
        rep["gap_mm_median"] = float(np.median(P["gap"][ok])) if ok.any() else None
        RA, RB = planes["A"].direct, planes["B"].direct
        theta = np.arccos(np.clip(np.median(RA.d, 0) @ np.median(RB.d, 0)
                                  / np.linalg.norm(np.median(RA.d, 0)) / np.linalg.norm(np.median(RB.d, 0)), -1, 1))
        rep["crossing_elongation_mm"] = float(beam_mm / np.sin(theta / 2))
    else:
        c, r, d, ok0 = planes[mode].nearest(X)
        ok = ok0 & (d <= tol_mm)
        draw(frame, c[ok], r[ok], wc, wr)
        rep[mode] = {"placed": int(ok.sum()), "dist_mm_median": float(np.median(d[ok])) if ok.any() else None}
        rep["placed"], rep["dropped"] = int(ok.sum()), int((~ok).sum())
    rep["on_fraction"] = float((frame > 0).mean())
    return frame, rep


def _qgrid(case: Case, step):
    lo, hi = case.t, case.S - case.t
    n = int(np.ceil((hi - lo) / step)) + 1
    return np.linspace(lo, hi, n)            # includes both walls exactly


def coverage(case: Case, planes: dict, y=None, step=0.5, tol_mm=0.35):
    """Plan-view reachability at height y: 0 none, 1 A only, 2 B only, 3 both (direct legs).
    Grid in (qa, qb) mm, rows = qb, cols = qa, walls sampled exactly."""
    C, uA, uB = case.axes()
    y = (case.y_base + case.y_top) / 2 if y is None else y
    q = _qgrid(case, step)
    QA, QB = np.meshgrid(q, q)
    X = C + QA.ravel()[:, None] * uA + QB.ravel()[:, None] * uB
    X[:, 1] = y
    m = np.zeros(len(X), np.uint8)
    for bit, f in ((1, "A"), (2, "B")):
        _, _, d, ok = planes[f].nearest(X)
        m |= (ok & (d < tol_mm)).astype(np.uint8) * bit
    return m.reshape(QA.shape), q


def joint_box(case: Case, planes: dict, heights=None, step=0.5):
    """Largest (qa, qb) square ANYWHERE in plan whose sample points (edges included) both families reach at
    every checked height. Side = (k - 1) * step for a k x k block of checked samples, so it never claims
    more than it checked (review). Returns (centre_world, side_mm, both_mask, q)."""
    C, uA, uB = case.axes()
    heights = heights if heights is not None else np.linspace(case.y_top + 2, case.y_base - 2, 13)
    both = None
    for y in heights:
        m, q = coverage(case, planes, y, step=step)
        both = (m == 3) if both is None else both & (m == 3)
    # largest all-True square (DP); dp[i, j] = side (in samples) of the square ending at (i, j)
    dp = np.zeros(both.shape, int)
    for i in range(both.shape[0]):
        for j in range(both.shape[1]):
            if both[i, j]:
                dp[i, j] = 1 if i == 0 or j == 0 else 1 + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    k = int(dp.max())
    if k < 2:
        return None, 0.0, both, q
    i, j = np.unravel_index(np.argmax(dp), dp.shape)
    qb_c = (q[i] + q[i - k + 1]) / 2
    qa_c = (q[j] + q[j - k + 1]) / 2
    centre = C + qa_c * uA + qb_c * uB
    centre[1] = (case.y_base + case.y_top) / 2
    return centre, float((k - 1) * (q[1] - q[0])), both, q


# ---------------------------------------------------------------- content
def cube_points(case: Case, side=30.0, yaw_deg=0.0, step=0.5, centre=None):
    """Wireframe cube in the liquid, edges sampled every `step` mm. yaw 0 = faces parallel to the walls."""
    c0, uA, uB = liquid_frame(case)
    if centre is not None:
        c0 = np.asarray(centre, float)
    a = np.radians(yaw_deg)
    e1 = np.cos(a) * uA + np.sin(a) * uB
    e2 = -np.sin(a) * uA + np.cos(a) * uB
    e3 = np.array([0.0, 1.0, 0.0])
    h = side / 2
    V = [c0 + h * (sx * e1 + sy * e2 + sz * e3) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    edges = [(i, j) for i in range(8) for j in range(i + 1, 8)
             if np.isclose(np.linalg.norm(V[i] - V[j]), side)]
    pts = []
    for i, j in edges:
        n = max(2, int(np.ceil(side / step)) + 1)
        pts.append(np.linspace(V[i], V[j], n))
    return np.concatenate(pts), np.array(V), edges


def helix_points(case: Case, centre, radius, pitch_mm=20.0, phase_deg=0.0, dy=0.4, margin_y=4.0):
    """One point per height: the ghost-free content class for two horizontally separated ray families.
    (Both families lie in near-horizontal fans, so all A and B rays at one height are coplanar: n points
    sharing a height light n^2 crossings, and a horizontal line lights a whole plane. A curve that is
    single-valued in height has exactly one A ray and one B ray per height, hence one crossing.)"""
    _, uA, uB = case.axes()
    ys = np.arange(case.y_top + margin_y, case.y_base - margin_y, dy)
    th = np.radians(phase_deg) + 2 * np.pi * (ys - ys[0]) / pitch_mm
    X = centre[None, :] + radius * (np.cos(th)[:, None] * uA + np.sin(th)[:, None] * uB)
    X[:, 1] = ys
    return X


def lattice_points(case: Case, both, q, spacing=5.0, margin_y=6.0):
    """3D lattice of crossing points on every `spacing` mm inside the jointly reachable plan region."""
    C, uA, uB = case.axes()
    step = q[1] - q[0]
    k = max(1, int(round(spacing / step)))
    ib, ia = np.nonzero(both)
    sel = (ia % k == 0) & (ib % k == 0)
    ys = np.arange(case.y_top + margin_y, case.y_base - margin_y + 1e-9, spacing)
    out = []
    for a, b in zip(ia[sel], ib[sel]):
        for y in ys:
            x = C + q[a] * uA + q[b] * uB
            x[1] = y
            out.append(x)
    return np.array(out)
