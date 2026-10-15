"""
Volume player: refresh rate + duty cycle for volumetric animation in the fluorescent case.

Duty: every element (a rod or a filled band of mirrors at one layer) carries a duty in [0, 1] = its share of
full glow. Duty -> blue level through the MEASURED glow curve (vol2/calib_duty, runs/*_duty/duty_roi.json, else data/calibration/duty_roi.json:
dead zone below ~48, ~(v/255)^2.6 above). Absorption: the fluorescein fades the beams (Joey: "about the
centre"), so an element at depth tau from its entry face gets duty x exp(tau / L) (L = absorption length,
default 30 mm, [HEURISTIC] until measured), renormalised so the scene's maximum is 1.
Refresh: frames are rendered up front and pushed on a fixed clock (default 60 Hz = the HDMI rate; the
window loop measured 225 pushes/s, so the DMD's 60 Hz is the limit). Late frames are dropped, not delayed;
the achieved rate and drops are reported. STOP file ends playback at once. Rig lock held while playing.
Modes: "ab" = bands from face A and face B (strongest volume); "b" = face B only (face A stays a clean
output window, shape extruded along B).

  python -m vol2.volplay <scene> [--fps 60] [--seconds 20] [--mode ab|b] [--L 30] [--dry]
  scenes: ball_bounce, ball_pulse, tower_twist, layer_scan, orbit (solids, pose-fit dependent)
          wave_A, waves_AB, ribbon (curtains designed in DMD space: rippling / crossing / twisting light sheets)
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rig import config as rig_config  # noqa: E402 - paths only, no hardware

from .geometry import Case  # noqa: E402
from .render import H, W, Plane  # noqa: E402
from .rods import family_axes  # noqa: E402
from .run import N_LIQ  # noqa: E402
from .solid import PROFILES  # noqa: E402

STOP = ROOT / "STOP"


# ---------------------------------------------------------------- duty -> blue level
BUNDLED = ROOT / "data" / "calibration"   # the 2026-10-05 rig's measurements, used when runs/ has none


def load_duty_lut(path=None):
    """Newest runs/*_duty/duty_roi.json (a fresh python -m vol2.calib_duty duty), else the bundled curve."""
    if path is None:
        runs = sorted(glob.glob(str(rig_config.RUNS / "*_duty" / "duty_roi.json")))
        path = runs[-1] if runs else str(BUNDLED / "duty_roi.json")
    rel = json.loads(Path(path).read_text(encoding="utf-8-sig"))["relative_glow"]
    v = np.array(sorted(int(k) for k in rel), float)
    g = np.array([max(0.0, rel[str(int(k))]) for k in v])
    g = np.maximum.accumulate(g)                         # monotone
    return v, g, _repo_rel(path)


def _repo_rel(path):
    """Repo-relative when inside the repo, so logs never record a local absolute path."""
    p = Path(path).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name


def duty_to_level(duty, lut):
    v, g, _ = lut
    d = np.clip(duty, 0, 1)
    lv = np.interp(d, g, v)
    return np.where(d <= 0, 0, np.clip(np.round(lv), 0, 255)).astype(np.uint8)


# ---------------------------------------------------------------- scene elements
class Volume:
    def __init__(self, case_json, fill="glycerin", where=(40.0, 40.0), mode="ab", L=30.0):
        over = json.loads(Path(case_json).read_text(encoding="utf-8-sig"))
        over = {k: (tuple(v) if isinstance(v, list) else v) for k, v in over.items()}
        self.case = Case(**{"n_liq": N_LIQ[fill], "back_walls": "tir", **over})
        self.planes = {f: Plane(self.case, f) for f in ("A", "B")}
        self.axes = family_axes(self.planes)
        C, self.uA, self.uB = self.case.axes()
        self.centre = C + where[0] * self.uA + where[1] * self.uB
        self.mid = (self.case.y_base + self.case.y_top) / 2
        self.centre[1] = self.mid
        self.fams = ("A", "B") if mode == "ab" else ("B",)
        self.L = L

    def band(self, fam, centre, y, size, step=0.3, tol=0.8):
        """Mirrors of family fam whose rays pass within +/- size/2 of centre at height y, and the mean
        depth (mm from the entry face) at which they cross it."""
        P = self.planes[fam]
        perp = self.axes[fam][1]
        offs = np.arange(-size / 2, size / 2 + 1e-9, step) if size > 0 else np.array([0.0])
        pts = centre[None, :] + offs[:, None] * perp[None, :]
        pts[:, 1] = y
        idx, d = P.nearest_k(pts, 1)
        ok = np.isfinite(d[:, 0]) & (d[:, 0] <= tol)
        if not ok.any():
            return [], 0.0
        R = P.direct
        i = idx[ok, 0]
        tau = np.einsum("nk,nk->n", pts[ok] - R.p0[i], R.d[i])
        return list(zip(R.cols[i].astype(int), R.rows[i].astype(int))), float(np.mean(tau))

    def band_graded(self, fam, centre, y, size, step=0.3, tol=0.8, power=1.0):
        """Like band(), but each mirror gets duty (1 - (2o/size)^2)^power by its offset o across the band, so
        the two faces' graded bands add up to a rounded (elliptical) bright core instead of a sharp rhombus."""
        P = self.planes[fam]
        perp = self.axes[fam][1]
        offs = np.arange(-size / 2, size / 2 + 1e-9, step) if size > 0 else np.array([0.0])
        pts = centre[None, :] + offs[:, None] * perp[None, :]
        pts[:, 1] = y
        idx, d = P.nearest_k(pts, 1)
        ok = np.isfinite(d[:, 0]) & (d[:, 0] <= tol)
        R = P.direct
        out = []
        for o, i, k in zip(offs, idx[:, 0], ok):
            if not k:
                continue
            w = max(0.0, 1 - (2 * o / size) ** 2) ** power if size > 0 else 1.0
            tau = float((pts[0] - R.p0[i]) @ R.d[i]) if False else float(((centre - R.p0[i]) @ R.d[i]))
            out.append(([(int(R.cols[i]), int(R.rows[i]))], w, tau))
        return out

    def sphere(self, cy, radius, duty=1.0, offset=None, dy=0.8, power=1.0):
        """Rounded solid: layer size follows the sphere, duty grades across each band and falls off toward
        the poles, so the summed glow approximates an ellipsoid (stretched along the families' bisector)."""
        els = []
        for y in np.arange(cy - radius, cy + radius + 1e-9, dy):
            h = (y - cy) / radius
            s = 2 * radius * np.sqrt(max(0.0, 1 - h * h))
            if s <= 0.3:
                continue
            c0 = self.centre + (offset if offset is not None else 0.0)
            for f in self.fams:
                for m, w, tau in self.band_graded(f, c0, y, s, power=power):
                    els.append((m, duty * w * (0.6 + 0.4 * (1 - h * h)), tau))
        return els

    def solid(self, profile, y_lo, y_hi, size, duty=1.0, offset=None, dy=1.0):
        """Elements (mirrors, duty, depth) for a solid between y_lo and y_hi."""
        els = []
        ys = np.arange(y_lo, y_hi + 1e-9, dy)
        n = max(len(ys) - 1, 1)
        for k, y in enumerate(ys):
            s = size * profile(k / n)
            if s <= 0.05:
                continue
            c0 = self.centre + (offset if offset is not None else 0.0)
            for f in self.fams:
                m, tau = self.band(f, c0, y, s)
                if m:
                    els.append((m, duty, tau))
        return els

    def frame(self, elements, lut, wc=3, wr=5):
        """Rasterise elements into a blue-only BGR frame. Overlapping blocks take the max duty."""
        dmap = np.zeros((H, W), np.float32)
        comp = [d * np.exp(t / self.L) for _, d, t in elements]
        norm = max(comp) if comp else 1.0
        for (mirrors, _, _), dc in zip(elements, comp):
            dd = dc / norm
            for c, r in mirrors:
                sl = (slice(max(0, r - wr // 2), min(H, r + wr // 2 + 1)), slice(max(0, c - wc // 2), min(W, c + wc // 2 + 1)))
                dmap[sl] = np.maximum(dmap[sl], dd)
        f = np.zeros((H, W, 3), np.uint8)
        f[..., 0] = duty_to_level(dmap, lut)
        return f, norm


# ---------------------------------------------------------------- scenes: t (s) -> elements
def scene_fn(vol: Volume, name, size=7.0, height=14.0):
    top, bot = vol.case.y_top + 4, vol.case.y_base - 4
    mid = vol.mid
    if name == "ball_bounce":                                   # solid ball bounces top <-> bottom, 1.6 s period
        bh = 0.45 * height

        def f(t):
            cy = top + bh / 2 + (bot - top - bh) * (0.5 - 0.5 * np.cos(2 * np.pi * t / 1.6))
            return vol.solid(PROFILES["ball"], cy - bh / 2, cy + bh / 2, size)
        return f
    if name == "sphere_round":                                  # static rounded sphere (graded duty)
        def f(t):
            return vol.sphere(mid, 0.5 * size)
        return f
    if name == "sphere_pulse":                                  # rounded sphere whose size and duty breathe
        def f(t):
            k = 0.75 + 0.25 * np.sin(2 * np.pi * t)
            return vol.sphere(mid, 0.5 * size * k, duty=0.5 + 0.5 * k)
        return f
    if name == "sphere_bounce":                                 # rounded sphere bouncing top <-> bottom
        def f(t):
            r = 0.5 * size
            cy = top + r + (bot - top - 2 * r) * (0.5 - 0.5 * np.cos(2 * np.pi * t / 1.6))
            return vol.sphere(cy, r)
        return f
    if name == "ball_pulse":                                    # brightness (duty) breathes at 1 Hz
        def f(t):
            return vol.solid(PROFILES["ball"], mid - height / 2, mid + height / 2, size,
                             duty=0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * t)))
        return f
    if name == "tower_twist":                                   # solid slices orbiting with height-dependent phase
        def f(t):
            els = []
            ys = np.arange(top, bot + 1e-9, 1.0)
            for k, y in enumerate(ys):
                ph = 2 * np.pi * (t / 2.0 + 0.5 * k / len(ys))
                off = 1.8 * (np.cos(ph) * vol.uA + np.sin(ph) * vol.uB)
                for fam in vol.fams:
                    m, tau = vol.band(fam, vol.centre + off, y, 0.5 * size)
                    if m:
                        els.append((m, 1.0, tau))
            return els
        return f
    if name == "layer_scan":                                    # a bright solid slab sweeps down with a fading trail
        def f(t):
            pos = top + (bot - top) * ((t / 2.0) % 1.0)
            els = []
            for k in range(6):
                y = pos - 1.5 * k
                if y < top:
                    break
                els += vol.solid(PROFILES["cube"], y - 0.5, y + 0.5, size, duty=0.85 ** (2 * k))
            return els
        return f
    if name == "orbit":                                         # a small solid ball orbiting the centre
        def f(t):
            ph = 2 * np.pi * t / 2.0
            off = 3.0 * (np.cos(ph) * vol.uA + np.sin(ph) * vol.uB)
            return vol.solid(PROFILES["ball"], mid - 4, mid + 4, 4.0, offset=off)
        return f
    # ---- curtains: one column per DMD row = a sheet through the volume (a ruled surface of that face's rays).
    # Designed directly in DMD space, so they do not depend on the pose fit. Columns stay inside the clean
    # windows (A <= 645, B >= 695 per case_fit_tank_v4); rows span the liquid.
    rows = np.arange(int(vol.case.rows[0]), int(vol.case.rows[1]) + 1)
    winA, winB = (588, 643), (697, 748)

    def curtain(win, phase_cols, width=3):
        c0, c1 = win
        mid_c, amp = (c0 + c1) / 2, (c1 - c0) / 2 - width
        cols = np.clip(np.round(mid_c + amp * phase_cols), c0, c1).astype(int)
        return [(int(c) + k, int(r)) for c, r in zip(cols, rows) for k in range(-(width // 2), width // 2 + 1)]

    lam = 120.0                                              # rows per wavelength (~24 mm at ~5 rows/mm)
    if name == "wave_A":                                     # one rippling curtain from face A
        def f(t):
            return [(curtain(winA, np.sin(2 * np.pi * (rows / lam - 0.8 * t))), 1.0, 0.0)]
        return f
    if name == "waves_AB":                                   # two rippling curtains; their crossing line moves
        def f(t):
            return [(curtain(winA, np.sin(2 * np.pi * (rows / lam - 0.8 * t))), 1.0, 0.0),
                    (curtain(winB, np.sin(2 * np.pi * (rows / lam + 0.6 * t))), 1.0, 0.0)]
        return f
    # ocean (Joey: "level ocean waves through it, a flat 3D wave scene"): each face's columns carry a height field.
    # Column c lights a short block of rows centred at r(c, t) = r_mean + amp * h(c, t); every lit mirror is a ray
    # through the liquid at that height, so the lit set is a corrugated sheet (crests along that face's rays) that
    # rolls as h moves. Crest duty is higher (foam). Designed in DMD space: pose independent.
    r_mean = 0.5 * (rows[0] + rows[-1])

    def sea(win, t, amp_rows, comps, thick=4):
        els = []
        c0, c1 = win
        cols = np.arange(c0, c1 + 1)
        h = np.zeros(len(cols))
        for a, lam_cols, cyc_s in comps:                 # (relative amplitude, wavelength in columns, cycles/s)
            h += a * np.sin(2 * np.pi * (cols / lam_cols - cyc_s * t))
        h /= max(sum(abs(a) for a, _, _ in comps), 1e-9)
        rr = np.round(r_mean - amp_rows * h).astype(int)  # y is down: crest = smaller row = higher
        for c, r, hh in zip(cols, rr, h):
            mirrors = [(int(c), int(r + k)) for k in range(-(thick // 2), thick - thick // 2)]
            els.append((mirrors, 0.55 + 0.45 * (hh + 1) / 2, 0.0))
        return els

    seas = {
        "ocean_swell": (("A",), 30, [(1.0, 40, 0.6), (0.35, 17, 1.1)]),
        "ocean": (("A", "B"), 34, [(1.0, 36, 0.6), (0.4, 15, -0.9), (0.2, 9, 1.7)]),
        "ocean_storm": (("A", "B"), 55, [(1.0, 30, 1.0), (0.6, 13, -1.6), (0.35, 7, 2.4)]),
    }
    if name in seas:
        faces, amp, comps = seas[name]

        def f(t):
            els = []
            for fam in faces:
                win = winA if fam == "A" else winB
                cps = comps if fam == "A" else [(a, lmb * 0.9, -s * 0.8) for a, lmb, s in comps]
                els += sea(win, t, amp, cps)
            return els
        return f

    # flat planes: every column of both windows at one row band -> a horizontal sheet of light from each face,
    # together one flat plane through the liquid (DMD space; a row maps to ~one height across the case).
    def plane(t, row_of_col, thick=4):
        els = []
        for win in (winA, winB):
            cols = np.arange(win[0], win[1] + 1)
            rr = np.round(row_of_col(cols, t)).astype(int)
            els.append(([(int(c), int(r + k)) for c, r in zip(cols, rr)
                         for k in range(-(thick // 2), thick - thick // 2)], 1.0, 0.0))
        return els

    span = 0.5 * (rows[-1] - rows[0]) - 8
    planes_ = {
        "plane_flat": lambda cols, t: np.full(len(cols), r_mean),
        "plane_sweep": lambda cols, t: np.full(len(cols), r_mean + span * np.sin(2 * np.pi * t / 4.0)),
        "plane_tilt": lambda cols, t: r_mean + 0.6 * (cols - cols.mean()),
    }
    if name in planes_:
        fn_rows = planes_[name]
        return lambda t: plane(t, fn_rows)

    # full-width planes (plane_geom 2026-10-05: blue, every column 560-785 INCLUDING the rounded corner, which
    # fills the gap between the faces; 12 rows -> 4.3x the clean-window glow, evenness 0.61; white adds glints).
    FW = np.arange(560, 786)
    r_top, r_bot = rows[0] + 10, rows[-1] - 10

    def fw(row_of_col, thick=12, duty=1.0):
        rr = np.round(row_of_col).astype(int) if np.ndim(row_of_col) else np.full(len(FW), int(round(row_of_col)))
        m = [(int(c), int(r + k)) for c, r in zip(FW, rr) for k in range(-(thick // 2), thick - thick // 2)]
        return (m, float(duty), 0.0)

    # warp-corrected planes (warp_scan 2026-10-05): rows chosen per column from the measured map so the plane is
    # straight and level AS SEEN FROM THE CAMERA / VIEWER. Targets are camera-image y values (pixels).
    if name.startswith("fwc_"):
        from .warp_scan import clean_map
        maps = sorted(rig_config.RUNS.glob("*_warp_scan/warp_map.npz"))    # newest COMPLETE scan, else bundled
        X, Y, cs_, rs_, keep = clean_map(maps[-1].parent if maps else BUNDLED / "warp_scan")
        ccols = [c for j, c in enumerate(cs_) if keep[j] and np.isfinite(Y[:, j]).sum() >= 3]
        fit = {}
        for j, c in enumerate(cs_):
            ok = np.isfinite(Y[:, j])
            if c in ccols:
                o = np.argsort(Y[ok, j])
                fit[c] = (Y[ok, j][o], rs_[ok].astype(float)[o], float(np.nanmedian(X[:, j])))
        allc = np.arange(min(ccols), max(ccols) + 1)
        xs_c = np.interp(allc, ccols, [fit[c][2] for c in ccols])          # camera x of every column

        def rows_for(y_of_x):
            """y_of_x: array of target camera y per column (by its camera x) -> DMD rows per column."""
            yt = y_of_x(xs_c)
            rr = []
            for c, y in zip(allc, yt):
                lo = max([cc for cc in ccols if cc <= c], default=ccols[0])
                hi = min([cc for cc in ccols if cc >= c], default=ccols[-1])
                ra = np.interp(y, fit[lo][0], fit[lo][1])
                rb = np.interp(y, fit[hi][0], fit[hi][1])
                w_ = 0.0 if hi == lo else (c - lo) / (hi - lo)
                rr.append((1 - w_) * ra + w_ * rb)
            return np.array(rr)

        y_mid = float(np.nanmedian(Y[np.argmin(np.abs(rs_ - r_mean)), keep]))
        y_lo = float(np.nanpercentile(Y[:, keep], 8))
        y_hi = float(np.nanpercentile(Y[:, keep], 85))

        def pl(y_of_x, thick=10, duty=1.0):
            rr = np.round(rows_for(y_of_x)).astype(int)
            return ([(int(c), int(r + k)) for c, r in zip(allc, rr) for k in range(-(thick // 2), thick - thick // 2)],
                    float(duty), 0.0)

        xm = float(xs_c.mean())
        if name == "fwc_static":
            return lambda t: [pl(lambda x: np.full(len(x), y_mid))]
        if name == "fwc_scan":
            return lambda t: [pl(lambda x: np.full(len(x), y_lo + (y_hi - y_lo) * (0.5 - 0.5 * np.cos(2 * np.pi * t / 3.0))))]
        if name == "fwc_stack":
            def f(t):
                n, ph = 4, (t % 6.0) / 6.0
                els = []
                for k in range(n):
                    on = np.clip((ph * 1.6 - k / n) * 5, 0, 1) * np.clip((1 - ph) * 6, 0, 1)
                    if on > 0.02:
                        yk = y_lo + (y_hi - y_lo) * (k + 0.5) / n
                        els.append(pl(lambda x, yk=yk: np.full(len(x), yk), thick=8, duty=on))
                return els
            return f
        if name == "fwc_rock":
            return lambda t: [pl(lambda x: y_mid + 0.12 * np.sin(2 * np.pi * t / 2.5) * (x - xm))]
        if name == "fwc_ripple":
            return lambda t: [pl(lambda x: y_mid + 5 * np.sin(2 * np.pi * ((x - xm) / 60.0 - 0.5 * t)), thick=8)]
        if name == "fwc_split":
            def f(t):
                dd = (y_hi - y_lo) * 0.4 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 3.0))
                return [pl(lambda x: np.full(len(x), y_mid - dd), thick=8), pl(lambda x: np.full(len(x), y_mid + dd), thick=8)]
            return f
        raise SystemExit(f"unknown scene {name}")

    if name == "fw_static":
        return lambda t: [fw(r_mean)]
    if name == "fw_scan":                                         # thick plane sweeping top <-> bottom, 3 s
        return lambda t: [fw(r_top + (r_bot - r_top) * (0.5 - 0.5 * np.cos(2 * np.pi * t / 3.0)))]
    if name == "fw_stack":                                        # floors build up one by one, hold, fade
        def f(t):
            n, ph = 5, (t % 6.0) / 6.0
            els = []
            for k in range(n):
                on = np.clip((ph * 1.6 - k / n) * 5, 0, 1) * np.clip((1 - ph) * 6, 0, 1)
                if on > 0.02:
                    els.append(fw(r_top + (r_bot - r_top) * (k + 0.5) / n, thick=8, duty=on))
            return els
        return f
    if name == "fw_breathe":                                      # thickness and duty breathe at 0.5 Hz
        def f(t):
            s = 0.5 + 0.5 * np.sin(2 * np.pi * t / 2.0)
            return [fw(r_mean, thick=int(4 + 16 * s), duty=0.5 + 0.5 * s)]
        return f
    if name == "fw_rock":                                         # see-saw: tilt across the columns oscillates
        def f(t):
            slope = 0.35 * np.sin(2 * np.pi * t / 2.5)
            return [fw(r_mean + slope * (FW - FW.mean()))]
        return f
    if name == "fw_ripple":                                       # calm ripple on a strong plane
        def f(t):
            return [fw(r_mean + 10 * np.sin(2 * np.pi * (FW / 45.0 - 0.5 * t)), thick=10)]
        return f
    if name == "fw_split":                                        # one plane splits into two and re-merges
        def f(t):
            d = (r_bot - r_top) * 0.35 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 3.0))
            return [fw(r_mean - d, thick=10), fw(r_mean + d, thick=10)]
        return f
    if name == "fw_rain":                                         # thin sheets falling from the top, staggered
        def f(t):
            els = []
            for k in range(4):
                ph = ((t / 2.0) + k / 4.0) % 1.0
                els.append(fw(r_top + (r_bot - r_top) * ph ** 1.6, thick=4, duty=1.0 - 0.6 * ph))
            return els
        return f
    if name == "fw_ribbon":                                       # strong plane + the twisting ribbon curtains
        def f(t):
            u = (rows - rows[0]) / max(rows[-1] - rows[0], 1)
            return [fw(r_mean, thick=8, duty=0.8),
                    (curtain(winA, np.sin(2 * np.pi * (0.5 * u + 0.5 * t))), 1.0, 0.0),
                    (curtain(winB, np.cos(2 * np.pi * (0.5 * u + 0.5 * t))), 1.0, 0.0)]
        return f

    # ribbons (Joey's favourite: best structure and animation): each face's curtain sweeps across its window
    # with height (turns over the liquid height) and time (speed in cycles/s); n ribbons per face, evenly phased.
    ribbons = {"ribbon": (0.5, 0.5, 1), "ribbon_fast": (0.5, 1.0, 1), "ribbon_twist": (1.0, 0.5, 1),
               "ribbon_double": (0.75, 0.5, 2), "ribbon_cage": (0.75, 0.4, 3)}
    if name in ribbons:
        turns, speed, n = ribbons[name]
        u = (rows - rows[0]) / max(rows[-1] - rows[0], 1)

        def f(t):
            els = []
            for j in range(n):
                ph = j / n
                els.append((curtain(winA, np.sin(2 * np.pi * (turns * u + speed * t + ph))), 1.0, 0.0))
                els.append((curtain(winB, np.cos(2 * np.pi * (turns * u + speed * t + ph))), 1.0, 0.0))
            return els
        return f
    raise SystemExit(f"unknown scene {name}")


def render_clip(vol, name, fps, seconds, lut):
    fn = scene_fn(vol, name)
    n = int(round(fps * min(seconds, _period(name))))
    frames, norms = [], []
    for i in range(n):
        f, nm = vol.frame(fn(i / fps), lut)
        frames.append(f)
        norms.append(nm)
    return frames, norms


# scene -> loop period (s); SCENES is the registry the player and the tests use
PERIODS = {"ball_bounce": 1.6, "ball_pulse": 1.0, "tower_twist": 2.0, "layer_scan": 2.0, "orbit": 2.0,
           "wave_A": 1.25, "waves_AB": 5.0, "ribbon": 2.0, "ribbon_fast": 1.0, "ribbon_twist": 2.0,
           "ribbon_double": 2.0, "ribbon_cage": 2.5,
           "ocean_swell": 10.0, "ocean": 10.0, "ocean_storm": 10.0,
           "plane_flat": 0.5, "plane_sweep": 4.0, "plane_tilt": 0.5,
           "fw_static": 0.5, "fw_scan": 3.0, "fw_stack": 6.0, "fw_breathe": 2.0, "fw_rock": 2.5,
           "fw_ripple": 2.0, "fw_split": 3.0, "fw_rain": 2.0, "fw_ribbon": 2.0,
           "fwc_static": 0.5, "fwc_scan": 3.0, "fwc_stack": 6.0, "fwc_rock": 2.5, "fwc_ripple": 2.0, "fwc_split": 3.0,
           "sphere_round": 0.5, "sphere_pulse": 1.0, "sphere_bounce": 1.6}
SCENES = tuple(PERIODS)


def _period(name):
    return PERIODS[name]


def play(frames, fps, seconds):
    from rig.bench import Bench
    shown = dropped = 0
    elapsed = 0.0
    with Bench(camera=False, min_hold_s=0.0) as b:       # lock + window; DMD dark, lock released on any exit
        STOP.unlink(missing_ok=True)                     # we hold the rig: any STOP left over is stale
        try:
            dt = 1.0 / fps
            t0 = time.perf_counter()
            i = 0
            while time.perf_counter() - t0 < seconds and not STOP.exists():
                target = t0 + i * dt
                now = time.perf_counter()
                if now > target + dt:                    # late by a whole frame: skip it
                    dropped += 1
                    i += 1
                    continue
                while time.perf_counter() < target:
                    cv2.waitKey(1)                       # pumped wait, never a bare sleep
                b.window.show(frames[i % len(frames)])
                shown += 1
                i += 1
            elapsed = time.perf_counter() - t0
        finally:
            STOP.unlink(missing_ok=True)                 # only ever our own STOP: we hold the rig here
    return {"target_fps": fps, "achieved_fps": round(shown / max(elapsed, 1e-9), 1), "shown": shown,
            "dropped": dropped, "seconds": round(elapsed, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--fps", type=float, default=60.0)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--mode", default="ab", choices=["ab", "b"])
    ap.add_argument("--L", type=float, default=30.0)
    ap.add_argument("--case-json", default=str(ROOT / "configs" / "case_fit_tank_v4.json"))
    ap.add_argument("--where", default="40,40")
    ap.add_argument("--dry", action="store_true", help="render and save frames only")
    a = ap.parse_args()
    lut = load_duty_lut()
    vol = Volume(a.case_json, where=tuple(float(v) for v in a.where.split(",")), mode=a.mode, L=a.L)
    t0 = time.perf_counter()
    frames, norms = render_clip(vol, a.scene, a.fps, a.seconds, lut)
    out = ROOT / "vol2" / "out" / "volplay" / f"{a.scene}_{a.mode}_{int(a.fps)}fps"
    out.mkdir(parents=True, exist_ok=True)
    for k in np.linspace(0, len(frames) - 1, min(16, len(frames))).astype(int):   # 16 samples for camera GIFs
        cv2.imwrite(str(out / f"f{k:03d}.png"), frames[k])
    info = {"scene": a.scene, "mode": a.mode, "fps": a.fps, "frames_per_cycle": len(frames),
            "render_s": round(time.perf_counter() - t0, 1), "L_mm": a.L, "duty_lut": lut[2],
            "max_blue_level": int(max(f[..., 0].max() for f in frames))}
    print(json.dumps(info), flush=True)
    if not a.dry:
        info["playback"] = play(frames, a.fps, a.seconds)
        print(json.dumps(info["playback"]), flush=True)
    (out / "info.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
