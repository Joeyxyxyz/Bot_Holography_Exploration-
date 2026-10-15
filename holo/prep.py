"""
OGR brief tasks T2, T3, T4 — offline, no hardware. (The cube hologram is fresnel_cube.py.)

  T2  f_c x fill_fraction x gs_iters sweep, +1-order correlation (validate.py's END-TO-END metric)
  T3  light budget for the lensless LED route (and a laser reference), assumptions listed in the output
  T4  diffraction-order prediction for the two lattice models the HDMI 912x1140 frame can map to:
        rect    : 10.8 um (x) x 5.4 um (y), no row offset (what the scanner's camera parity test saw)
        diamond : same pitches, alternate rows shifted 5.4 um (centred-rectangular; TI active area
                  912 x 10.8 um = 9.85 mm, 1140 x 5.4 um = 6.16 mm)
      NB the package's "orthogonal 7.56 um square" model is NOT one of these: the active-area
      dimensions rule it out, so T4 is re-posed here on the two models that fit the datasheet.

Everything here is SIMULATION or arithmetic. [PROVED] = computed; nothing is measured.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

OGR = Path(__file__).resolve().parents[1] / "third_party" / "OGR_DMD_MathPackage_v1.0"
sys.path.insert(0, str(OGR))
from ogr import lee, pipeline  # noqa: E402
from ogr.fourier import intensity, reconstruct  # noqa: E402

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
N = 1024
LAM = 532e-9


# ---------------------------------------------------------------- T2
def plus1_corr(B, target, f_c):
    """validate.py's END-TO-END metric: window at the +1 order vs the target glyph."""
    img = intensity(reconstruct(B.astype(float)))
    s = target.shape[0]
    cj = N // 2 + int(f_c * N)
    r = s // 2
    win = img[N // 2 - r:N // 2 + r, cj - r:cj + r]
    win = win / max(win.max(), 1e-30)
    tgt = target[np.arange(win.shape[0]) * s // win.shape[0]][:, np.arange(win.shape[1]) * s // win.shape[1]]
    return float(np.corrcoef(win.ravel(), tgt.ravel())[0, 1])


def t2_sweep():
    rows = []
    for f_c in (0.0625, 0.125, 0.25):
        for fill in (0.05, 0.125, 0.25):
            for gs in (0, 10, 40):
                g = pipeline.text_glyph("X", int(N * fill))
                c = np.zeros((N, N))
                c0 = (N - g.shape[0]) // 2
                c[c0:c0 + g.shape[0], c0:c0 + g.shape[0]] = g
                H = pipeline.gerchberg_saxton(c, iters=gs) if gs else pipeline.hologram_from_target(c)
                rows.append({"f_c": f_c, "fill": fill, "gs_iters": gs,
                             "corr": round(plus1_corr(lee.encode_field(H, f_c=f_c, axis="u"), g, f_c), 4),
                             "fill_le_1.33fc": fill <= 1.33 * f_c})
    return rows


# ---------------------------------------------------------------- T3
def t3_budget(eff_window=0.009, lines_mm=72.0):
    """Lensless route: source -> pinhole -> collimator -> DMD -> +1-order image (cube wireframe).
    eff_window: fraction of DMD-incident light landing in the image window (from fresnel_cube sims)."""
    A = {  # assumptions, all [HEURISTIC] unless noted
        "led_optical_W": 0.30, "led_die_mm2": 1.0, "led_fwhm_nm": 30.0,
        "collimator_f_mm": 100.0, "optics_transmission": 0.8,
        "dmd_area_mm2": 9.85 * 6.16,            # [PROVED] from 912 x 10.8 um, 1140 x 5.4 um
        "dmd_window_fill_reflect": 0.85,        # [ASSERTED] window x fill factor x mirror reflectance, typical
        "eff_window_from_sim": eff_window, "wireframe_length_mm": lines_mm,
        "white_card_reflectance": 0.9, "V_532": 0.88,
        "dark_visible_cd_m2": 0.01, "comfortable_cd_m2": 1.0,
    }
    L = A["led_optical_W"] / (math.pi * A["led_die_mm2"])       # W / (mm^2 sr), Lambertian
    rows = []
    for name, d_um, fwhm in (("led_pin75_nofilter", 75, 30), ("led_pin75_10nm", 75, 10),
                             ("led_pin200_nofilter", 200, 30), ("led_pin200_10nm", 200, 10),
                             ("laser_5mW", None, None)):
        if d_um is None:
            P_dmd = 5e-3 * A["optics_transmission"]
            blur_mm = 0.0
        else:
            theta = d_um * 1e-3 / (2 * A["collimator_f_mm"])
            G = A["dmd_area_mm2"] * math.pi * theta ** 2          # mm^2 sr (etendue at the DMD)
            P_dmd = L * G * (fwhm / A["led_fwhm_nm"]) * A["optics_transmission"]
            blur_mm = 400 * theta                                  # z*theta at 0.40 m
        P_img = P_dmd * A["dmd_window_fill_reflect"] * A["eff_window_from_sim"]
        width_mm = max(0.06, 2 * blur_mm)
        E = P_img / (A["wireframe_length_mm"] * width_mm) * 1e6   # W/m^2 on a card at the image
        Lv = 683 * A["V_532"] * E * A["white_card_reflectance"] / math.pi
        rows.append({"case": name, "P_at_dmd_uW": round(P_dmd * 1e6, 2), "P_in_image_nW": round(P_img * 1e9, 1),
                     "line_width_mm": round(width_mm, 3), "card_luminance_cd_m2": round(Lv, 3),
                     "visible_dark_room": Lv > A["dark_visible_cd_m2"],
                     "comfortable": Lv > A["comfortable_cd_m2"]})
    return {"assumptions": A, "rows": rows,
            "note": "Card luminance = image focused on a white card. In a scattering fill only the "
                    "scattered fraction reaches the eye: expect 10-100x dimmer. [HEURISTIC]"}


# ---------------------------------------------------------------- T4
def t4_orders(lam=LAM, z=0.5):
    out = {}
    bases = {"rect": ((10.8e-6, 0.0), (0.0, 5.4e-6)), "diamond": ((10.8e-6, 0.0), (5.4e-6, 5.4e-6))}
    for name, (a1, a2) in bases.items():
        Am = np.array([a1, a2]).T
        Bm = np.linalg.inv(Am).T                 # reciprocal basis (cycles / m), columns
        pts = []
        for m in range(-4, 5):
            for n in range(-4, 5):
                if m or n:
                    k = Bm @ np.array([m, n]) * lam  # direction sines
                    if np.hypot(*k) < 0.12:
                        pts.append((round(float(k[0] * z * 1e3), 1), round(float(k[1] * z * 1e3), 1)))
        pts = sorted(set(pts), key=lambda q: (round(math.hypot(*q), 1), q))
        out[name] = {"nearest_orders_xy_mm": pts[:6], "z_m": z, "lambda_m": lam}
    out["discriminator"] = (
        "All mirrors ON, coherent (laser or pinhole-filtered LED) collimated beam on the bare DMD, "
        "screen at %.2f m around the ON-state specular spot. rect: first orders ON THE HORIZONTAL AXIS "
        "at +/-%.1f mm. diamond: first orders on the 45-deg DIAGONALS at (+/-%.1f, +/-%.1f) mm and "
        "nothing on the horizontal axis until +/-%.1f mm. [PROVED] for these lattice models."
        % (z, lam * z / 10.8e-6 * 1e3, lam * z / 10.8e-6 * 1e3, lam * z / 10.8e-6 * 1e3, lam * z / 5.4e-6 * 1e3))
    return out


def main():
    t0 = time.time()
    eff = 0.009
    fr = OUT / "cube3d_report.json"
    if fr.exists():                      # use the best-lit design's simulated efficiency if available
        rep_c = json.loads(fr.read_text())
        effs = [v["eff_window"][1] for v in rep_c.get("clip_frontier", {}).values()]
        eff = max(effs) if effs else rep_c["sims"]["design-diamond_truth-diamond"]["eff_window"][1]
    rep = {"T2": t2_sweep(), "T3": t3_budget(eff), "T4": t4_orders(), "runtime_s": None}
    rep["runtime_s"] = round(time.time() - t0, 1)
    (OUT / "prep_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({"T3": rep["T3"]["rows"], "T4": rep["T4"]}, indent=1))


if __name__ == "__main__":
    main()
