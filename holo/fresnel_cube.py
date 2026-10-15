"""
Real (coherent) volumetric hologram of a cube for the DLP4500 — design + simulation, no hardware.

Geometry (lensless Fresnel, corrections #1/#2 respected):
  collimated laser -> bare DMD -> free space -> image layers at z1 < z2 < z3 (default 0.38/0.40/0.42 m)
  Each layer is a REAL image formed by the hologram's own encoded focusing (Fresnel transform),
  so depth is carried by quadratic phase, not by carriers.
Physical sampling: the DMD is modelled on a 5.4 um cell grid (1140 rows x 1824 cells, 9.85 x 6.16 mm).
  One mirror = 2 cells wide x 1 row (10.8 x 5.4 um = one mirror's area).
  Lattice models (T4 decides which is true on this unit):
    "diamond": rows with r % 2 == 1 shifted right by one cell (centred-rectangular, TI geometry)
    "rect":    no shift (what the scanner's camera-level parity test reported)
Encoding: multi-plane Gerchberg-Saxton field (aperture-limited) -> Lee binary (ogr.lee.encode),
  carrier along x at F_C cycles/cell; mirror value sampled at its left cell.
Simulation: the ACTUAL 1-bit mirror pattern (both lattice models, matched and mismatched)
  Fresnel-propagated to every plane; the +1-order window correlated with each layer target.

Tags: all numbers here are [PROVED] only as computations of this model; nothing is measured.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

OGR = Path(__file__).resolve().parents[1] / "third_party" / "OGR_DMD_MathPackage_v1.0"
sys.path.insert(0, str(OGR))
from ogr import bmp, lee  # noqa: E402

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

LAM = 532e-9                 # green laser (Joey decides the source; re-run with --lam for others)
CELL = 5.4e-6                # half column pitch = row pitch
ROWS, MCOLS = 1140, 912
CCOLS = 2 * MCOLS            # 1824 cells
NY, NX = 2048, 4096          # padded propagation grid (11.1 x 22.1 mm)
F_C = 0.20                   # carrier, cycles per cell along x (period 27 um = 2.5 mirror columns)
ZS = (0.38, 0.40, 0.42)      # layer planes (m); 20 mm spacing ~ axial resolution along the short axis
SIDE_MM = 6.0                # cube edge
LINE_MM = 0.06
GS_ITERS = 15
SEED = 0


# ---------------------------------------------------------------- optics
def _axes(n, d):
    return (np.arange(n) - n // 2) * d


def fresnel_fwd(U, z):
    x, y = _axes(NX, CELL), _axes(NY, CELL)
    cin = np.exp(1j * np.pi / (LAM * z) * (y[:, None] ** 2 + x[None, :] ** 2)).astype(np.complex64)
    F = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(U * cin)))
    du, dv = LAM * z / (NX * CELL), LAM * z / (NY * CELL)
    u, v = _axes(NX, du), _axes(NY, dv)
    cout = np.exp(1j * np.pi / (LAM * z) * (v[:, None] ** 2 + u[None, :] ** 2)).astype(np.complex64)
    return (F * cout).astype(np.complex64), du, dv


def fresnel_inv(Uz, z):
    x, y = _axes(NX, CELL), _axes(NY, CELL)
    du, dv = LAM * z / (NX * CELL), LAM * z / (NY * CELL)
    u, v = _axes(NX, du), _axes(NY, dv)
    cout = np.exp(-1j * np.pi / (LAM * z) * (v[:, None] ** 2 + u[None, :] ** 2)).astype(np.complex64)
    U = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(Uz * cout)))
    cin = np.exp(-1j * np.pi / (LAM * z) * (y[:, None] ** 2 + x[None, :] ** 2)).astype(np.complex64)
    return (U * cin).astype(np.complex64)


def x_off(z):
    """+1-order lateral offset at z from the carrier (sign fixed by simulation)."""
    return LAM * z * F_C / CELL


# ---------------------------------------------------------------- target
def cube_segments(side=SIDE_MM):
    """Wireframe split into 3 depth layers. Returns {layer_index: [((x0,y0),(x1,y1)), ...]} in mm."""
    h = side / 2
    fo, bo = np.array([-0.25, 0.25]) * side, np.array([0.25, -0.25]) * side
    corners = np.array([[-h, -h], [h, -h], [h, h], [-h, h]])
    F, B = corners + fo, corners * 0.95 + bo
    segs = {0: [], 1: [], 2: []}
    for i in range(4):
        segs[0].append((F[i], F[(i + 1) % 4]))
        segs[2].append((B[i], B[(i + 1) % 4]))
        a, b = F[i], B[i]
        segs[0].append((a, a + (b - a) / 3))
        segs[1].append((a + (b - a) / 3, a + 2 * (b - a) / 3))
        segs[2].append((a + 2 * (b - a) / 3, b))
    return segs


def render(segs, z, shift_mm=0.0):
    """Amplitude target on the Fresnel output grid of plane z (pitch du x dv), centred on axis."""
    du, dv = LAM * z / (NX * CELL), LAM * z / (NY * CELL)
    s = 4                                   # supersample for isotropic lines
    canvas = np.zeros((NY * s, NX * s // 2), np.uint8)   # pitch du/2 x dv/s ... keep aspect via separate scales
    sx, sy = canvas.shape[1] / (NX * du), canvas.shape[0] / (NY * dv)   # px per metre
    th = max(1, int(round(LINE_MM * 1e-3 * min(sx, sy))))
    for a, b in segs:
        p = [(int(round((q[0] * 1e-3 + shift_mm * 1e-3) * sx + canvas.shape[1] / 2)),
              int(round(q[1] * 1e-3 * sy + canvas.shape[0] / 2))) for q in (a, b)]
        cv2.line(canvas, p[0], p[1], 255, th, lineType=cv2.LINE_AA)
    T = cv2.resize(canvas.astype(np.float32) / 255, (NX, NY), interpolation=cv2.INTER_AREA)
    return T


# ---------------------------------------------------------------- DMD model
def aperture_mask():
    m = np.zeros((NY, NX), bool)
    y0, x0 = (NY - ROWS) // 2, (NX - CCOLS) // 2
    m[y0:y0 + ROWS, x0:x0 + CCOLS] = True
    return m, y0, x0


def shift_of(model):
    r = np.arange(ROWS)
    return (r % 2 == 1).astype(int) if model == "diamond" else np.zeros(ROWS, int)


def sample_mirrors(Bcell, model):
    """Cell-grid binary (ROWS x CCOLS) -> mirror frame (ROWS x MCOLS) for this lattice model."""
    s = shift_of(model)
    cols = 2 * np.arange(MCOLS)[None, :] + s[:, None]
    cols = np.clip(cols, 0, CCOLS - 1)
    return Bcell[np.arange(ROWS)[:, None], cols]


def raster_mirrors(M, model):
    """Mirror frame -> physical field on the padded cell grid (each mirror fills 2 cells)."""
    s = shift_of(model)
    cell = np.zeros((ROWS, CCOLS + 1), np.float32)
    cols = 2 * np.arange(MCOLS)[None, :] + s[:, None]
    r = np.arange(ROWS)[:, None]
    cell[r, cols] = M
    cell[r, cols + 1] = M
    U = np.zeros((NY, NX), np.complex64)
    _, y0, x0 = aperture_mask()
    U[y0:y0 + ROWS, x0:x0 + CCOLS] = cell[:, :CCOLS]
    return U


# ---------------------------------------------------------------- design
def design():
    rng = np.random.default_rng(SEED)
    segs = cube_segments()
    zmid = ZS[1]
    targets = [render(segs[k], z, shift_mm=-(x_off(z) - x_off(zmid)) * 1e3) for k, z in enumerate(ZS)]
    amps = [np.sqrt(t) for t in targets]
    ap, y0, x0 = aperture_mask()
    U0 = np.zeros((NY, NX), np.complex64)
    for A, z in zip(amps, ZS):
        U0 += fresnel_inv((A * np.exp(2j * np.pi * rng.random(A.shape))).astype(np.complex64), z)
    U0 *= ap
    hist = []
    for it in range(GS_ITERS):
        acc = np.zeros_like(U0)
        err = 0.0
        for A, z in zip(amps, ZS):
            Uz, _, _ = fresnel_fwd(U0, z)
            mag = np.abs(Uz)
            sc = (mag * A).sum() / max((A * A).sum(), 1e-30)
            err += float(np.corrcoef(mag.ravel()[::7], A.ravel()[::7])[0, 1])
            acc += fresnel_inv((A * sc * np.exp(1j * np.angle(Uz))).astype(np.complex64), z)
        U0 = (acc / len(ZS)) * ap
        hist.append(round(err / len(ZS), 4))
        print(f"  GS {it + 1}/{GS_ITERS} mean amp corr {hist[-1]}", flush=True)
    field = U0[y0:y0 + ROWS, x0:x0 + CCOLS]
    np.save(OUT / "cube3d_field.npy", field)
    return encode(field), targets, segs, hist


def encode(field, clip_pct=100.0):
    """Lee-encode; clip_pct < 100 saturates the amplitude at that percentile (more ON mirrors,
    more light, some fidelity cost)."""
    A = np.abs(field)
    A = np.minimum(A / max(np.percentile(A, clip_pct), 1e-30), 1.0)
    return lee.encode(A, np.angle(field), f_c=F_C, axis="u").astype(np.uint8)


# ---------------------------------------------------------------- evaluation
def window(I, z, xc_m, half_mm=6.0, out=256):
    du, dv = LAM * z / (NX * CELL), LAM * z / (NY * CELL)
    cx = int(round(xc_m / du + NX // 2))
    hx, hy = int(half_mm * 1e-3 / du), int(half_mm * 1e-3 / dv)
    crop = I[NY // 2 - hy:NY // 2 + hy, cx - hx:cx + hx]
    return cv2.resize(crop.astype(np.float32), (out, out), interpolation=cv2.INTER_AREA)


def evaluate(M, model, targets, tag):
    U = raster_mirrors(M, model)
    incident = float(aperture_mask()[0].sum())
    res = {"corr": [], "eff_window": [], "sign": None}
    planes = []
    Tw = None
    for i, z in enumerate(ZS):
        Uz, du, dv = fresnel_fwd(U, z)
        I = np.abs(Uz) ** 2
        if res["sign"] is None:                # which side the +1 order landed on
            e = [window(I, z, s * x_off(ZS[1])).sum() for s in (1, -1)]
            res["sign"] = 1 if e[0] >= e[1] else -1
        xc = res["sign"] * x_off(ZS[1])
        W = window(I, z, xc)
        Tw = [window(t, z, 0.0) for t in targets]
        if res["sign"] == -1:
            Tw = [t[:, ::-1] for t in Tw]     # conjugate order is mirrored
        res["corr"].append([round(float(np.corrcoef(W.ravel(), t.ravel())[0, 1]), 3) for t in Tw])
        # energy in the 12 mm window, as a fraction of light incident on the whole aperture
        hx, hy = int(6e-3 / du), int(6e-3 / dv)
        cx = int(round(xc / du + NX // 2))
        Ewin = I[NY // 2 - hy:NY // 2 + hy, cx - hx:cx + hx].sum()
        res["eff_window"].append(round(float(Ewin / (I.sum() / max(float((np.abs(U) ** 2).sum()), 1e-30)
                                                     * incident) ), 4))
        planes.append(W / max(W.max(), 1e-30))
    img = np.hstack([np.vstack([(p ** 0.5 * 255).astype(np.uint8) for p in planes]),
                     np.vstack([(t / max(t.max(), 1e-9) * 255).astype(np.uint8) for t in Tw])])
    cv2.imwrite(str(OUT / f"sim_{tag}.png"), img)
    return res


def main():
    t0 = time.time()
    Bcell, targets, segs, hist = design()
    rep = {"lambda_m": LAM, "cell_m": CELL, "f_c_cycles_per_cell": F_C, "layers_z_m": ZS,
           "cube_side_mm": SIDE_MM, "gs_iters": GS_ITERS, "gs_history": hist,
           "x_offset_mm_at_zmid": round(x_off(ZS[1]) * 1e3, 2),
           "axial_res_m": {ax: 2 * LAM / (a / (2 * ZS[1])) ** 2 for ax, a in
                           (("short_6.16mm", ROWS * CELL), ("long_9.85mm", CCOLS * CELL))},
           "lateral_res_um": {ax: LAM * ZS[1] / a * 1e6 for ax, a in
                              (("y", ROWS * CELL), ("x", CCOLS * CELL))},
           "sims": {}}
    for model in ("diamond", "rect"):
        M = sample_mirrors(Bcell, model)
        H = (M > 0).astype(np.uint8) * 255
        cv2.imwrite(str(OUT / f"cube3d_{model}_hdmi.png"), H)
        bmp.write_pattern(str(OUT / f"cube3d_{model}"), (H > 0).astype(np.uint8), both=True)
        rep[f"on_fraction_{model}"] = round(float(M.mean()), 4)
        for truth in ("diamond", "rect"):
            tag = f"design-{model}_truth-{truth}"
            rep["sims"][tag] = evaluate(M, truth, targets, tag)
            print(tag, rep["sims"][tag], flush=True)
    # brightness/fidelity frontier (diamond design, diamond truth); report, do not pick silently
    field = np.load(OUT / "cube3d_field.npy")
    rep["clip_frontier"] = {}
    for pct in (99.9, 99.0, 97.0, 90.0):
        M = sample_mirrors(encode(field, pct), "diamond")
        r = evaluate(M, "diamond", targets, f"clip{pct}")
        r["on_fraction"] = round(float(M.mean()), 4)
        rep["clip_frontier"][str(pct)] = r
        cv2.imwrite(str(OUT / f"cube3d_diamond_clip{pct}_hdmi.png"), (M > 0).astype(np.uint8) * 255)
        print("clip", pct, r, flush=True)
    for k, t in enumerate(targets):
        cv2.imwrite(str(OUT / f"cube3d_target_layer{k}.png"), (window(t, ZS[k], 0.0) * 255).astype(np.uint8))
    rep["runtime_s"] = round(time.time() - t0, 1)
    (OUT / "cube3d_report.json").write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: v for k, v in rep.items() if k != "sims"}, indent=1, default=float))


if __name__ == "__main__":
    main()
