"""
What a coherent build would need: LED -> pinhole -> collimator -> bare DMD -> lensless Fresnel image.
Design study only (BACKLOG item 9); no hardware, no FFTs. Joins the T3 light budget (prep.py) and
the LED coherence simulation (led_study.py) into one frontier: light in the image vs depth separation.

Model (paraxial, small source behind a collimator of focal length f; the DMD fills the beam):
  source half-angle   theta = d / (2 f)
  power on the DMD    P = L * A_dmd * pi theta^2 * (fwhm / LED fwhm) * T        (etendue; d, f only via theta)
  spatial smear       s_sp = z * theta                       (each tilt shifts the image; led_study.py)
  spectral smear      s_sp_x = x_off(z) * sigma_lam / lam      (the +1-order offset ~ lam, along x only)
  axial smear         dz_lam = z * sigma_lam / lam             (Fresnel focus ~ 1/lam)
  defocus blur        b = dz_layer * NA_short, NA_short = (ROWS*CELL/2) / z   (the cue that tells layers apart)
  depth ratio         R = sqrt(s_sp^2 + s_sp_x^2) / b    -> R < 0.5 separates, R < 2 partial, else none
The R thresholds are fitted to 22 led_study.py simulations [PROVED, simulation; HEURISTIC cut-offs]:
the 7 in hologram_led_study.json plus a 15-22 to 150 um, 3 and 10 nm sweep (2026-10-21,
hologram_led_study_small_pinholes.json). Simulated separation = diag - offdiag correlation;
'separates' > 0.15 (about 2/3 of the laser's 0.238), 'partial' > 0.03. Boundaries: R 0.631-0.661
and 1.36-1.57. tests/test_holo_build.py checks every simulation agrees.
Power and luminance use prep.py's [HEURISTIC] LED assumptions.
Everything else is [PROVED] only as arithmetic of this model; nothing is measured.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "out"

# same values as fresnel_cube.py (tests check they agree)
LAM = 532e-9
CELL = 5.4e-6
ROWS, CCOLS = 1140, 1824
F_C = 0.20
ZS = (0.38, 0.40, 0.42)
DZ_LAYER = ZS[1] - ZS[0]

# LED / optics assumptions: same as prep.t3_budget() [HEURISTIC]
A = {"led_optical_W": 0.30, "led_die_mm2": 1.0, "led_fwhm_nm": 30.0, "optics_transmission": 0.8,
     "dmd_area_mm2": 9.85 * 6.16, "dmd_window_fill_reflect": 0.85, "wireframe_length_mm": 72.0,
     "white_card_reflectance": 0.9, "V_532": 0.88, "dark_visible_cd_m2": 0.01, "comfortable_cd_m2": 1.0,
     "die_mm": 1.0}
# fraction of DMD light in the image window: clip-90 % design, fresnel_cube.py [PROVED, simulation]
EFF_WINDOW = 0.0446
LASER_W = 5e-3                   # reference laser, as prep.py
R_SEP, R_PARTIAL = 0.65, 1.6
DMD_DIAG_MM = math.hypot(9.85, 6.16)
ILLUM_DEG = 24.0                 # ON-state illumination angle, 2 x 12 deg tilt [ASSERTED, TI DLPC350 docs]


def x_off(z, lam=LAM):
    return lam * z * F_C / CELL


def na_short(z):
    return ROWS * CELL / 2 / z


def sigma_nm(fwhm_nm):
    return fwhm_nm / 2.3548


def budget(d_mm, f_mm, fwhm_nm, z=ZS[1]):
    """One build: pinhole d_mm, collimator f_mm, filter FWHM fwhm_nm (0 = laser line)."""
    theta = d_mm / (2 * f_mm)
    L = A["led_optical_W"] / (math.pi * A["led_die_mm2"])               # W/(mm^2 sr), Lambertian
    spec = min(1.0, fwhm_nm / A["led_fwhm_nm"]) if fwhm_nm else 1.0
    pin = min(1.0, (d_mm / A["die_mm"]) ** 2)                           # die imaged 1:1 overfills the pinhole
    P_dmd = L * A["dmd_area_mm2"] * math.pi * theta ** 2 * spec * A["optics_transmission"]
    if d_mm == 0:                                                        # laser reference, as prep.py
        P_dmd, pin = LASER_W * A["optics_transmission"], 1.0
    P_img = P_dmd * A["dmd_window_fill_reflect"] * EFF_WINDOW
    s_spatial = z * theta * 1e3                                          # mm
    rel = sigma_nm(fwhm_nm) * 1e-9 / LAM
    s_spec = x_off(z) * rel * 1e3
    dz_lam = z * rel * 1e3
    smear = math.hypot(s_spatial, s_spec)
    b = DZ_LAYER * na_short(z) * 1e3
    R = smear / b
    width = max(0.06, 2 * smear)
    E = P_img / (A["wireframe_length_mm"] * width) * 1e6                 # W/m^2 on a white card
    Lv = 683 * A["V_532"] * E * A["white_card_reflectance"] / math.pi
    return {"pinhole_mm": d_mm, "collimator_f_mm": f_mm, "filter_fwhm_nm": fwhm_nm,
            "theta_mrad": round(theta * 1e3, 4),
            "throughput_vs_bare_led": round(pin * spec, 6),
            "P_at_dmd_uW": round(P_dmd * 1e6, 3), "P_in_image_nW": round(P_img * 1e9, 2),
            "smear_spatial_mm": round(s_spatial, 4), "smear_spectral_x_mm": round(s_spec, 4),
            "axial_smear_mm": round(dz_lam, 2), "defocus_blur_mm": round(b, 4),
            "depth_ratio_R": round(R, 3), "verdict": verdict(R),
            "card_luminance_cd_m2": round(Lv, 4),
            "visible_dark_room": Lv > A["dark_visible_cd_m2"], "comfortable": Lv > A["comfortable_cd_m2"],
            "collimator_ok": f_mm >= collimator_min_f(),
            "transverse_coherence_mm": round(LAM / (2 * theta) * 1e3, 3) if theta else None}


def verdict(R):
    return "separates" if R < R_SEP else "partial" if R < R_PARTIAL else "none"


def collimator_min_f(f_number=2.0):
    """Shortest practical collimator: clear aperture covers the DMD seen at 24 deg, at f/2 [HEURISTIC]."""
    return f_number * DMD_DIAG_MM / math.cos(math.radians(ILLUM_DEG))


def theta_max(R_target, fwhm_nm, z=ZS[1]):
    """Largest source half-angle (rad) that keeps R below R_target; None if the filter alone fails."""
    b = DZ_LAYER * na_short(z)
    s_spec = x_off(z) * sigma_nm(fwhm_nm) * 1e-9 / LAM
    left = (R_target * b) ** 2 - s_spec ** 2
    return math.sqrt(left) / z if left > 0 else None


def frontier(f_mm=100.0):
    """For each filter and verdict: the largest pinhole (at f_mm) that still earns it, and its light."""
    rows = []
    for fwhm in (3.0, 10.0, 30.0):
        for name, R in (("separates", R_SEP), ("partial", R_PARTIAL)):
            th = theta_max(R * 0.99, fwhm)
            if th is None:
                rows.append({"filter_fwhm_nm": fwhm, "target": name, "pinhole_mm": None,
                             "why": "spectral smear alone exceeds the target"})
                continue
            d = 2 * th * f_mm
            rows.append({"target": name, **budget(round(d, 4), f_mm, fwhm)})
    return rows


def sim_check():
    """Every led_study.py simulation (f = 100 mm) vs this model's verdict."""
    out = {}
    for fn in ("hologram_led_study.json", "hologram_led_study_small_pinholes.json"):
        rep = json.loads((ROOT / "data/results" / fn).read_text())
        for k, c in rep["configs"].items():
            if k == "laser_532":
                d, fw = 0.0, 0.0
            else:
                fw = float(k.split("_")[1][:-2])
                p = k.split("_")[2]
                d = 1.0 if p == "bare" else int(p[3:-2]) / 1000
            sep = c["diag_mean"] - c["offdiag_mean"]
            sim = "separates" if sep > 0.15 else "partial" if sep > 0.03 else "none"
            m = budget(d, rep["f_col_mm"], fw)
            out[f"{fn.split('.')[0]}:{k}"] = {"sim_diag_minus_offdiag": round(sep, 3), "sim_verdict": sim,
                                              "model_R": m["depth_ratio_R"], "model_verdict": m["verdict"],
                                              "agree": sim == m["verdict"]}
    return out


def report():
    grid = [budget(d, f, fw) for f in (50.0, 100.0, 200.0) for d in (0.025, 0.05, 0.075, 0.1, 0.2)
            for fw in (3.0, 10.0, 30.0)]
    return {
        "date": "2026-10-21", "source": "holo/coherent_build.py (arithmetic model, no hardware)",
        "assumptions": {**A, "eff_window": EFF_WINDOW, "lambda_m": LAM, "layers_z_m": ZS,
                        "R_thresholds": [R_SEP, R_PARTIAL], "illum_deg": ILLUM_DEG},
        "collimator_min_f_mm": round(collimator_min_f(), 1),
        "laser_reference": budget(0.0, 100.0, 0.0),
        "sim_check": sim_check(), "frontier_f100": frontier(), "grid": grid,
        "notes": [
            "Light and spatial smear both depend only on theta = d/2f: a longer collimator with a "
            "proportionally larger pinhole gives the same light and the same blur [PROVED, model].",
            "The depth cue is the defocus of the other layers, dz * NA = 0.15 mm here. With a 10 nm "
            "filter at f = 100 mm: clean separation up to about a 37 um pinhole, partial up to about "
            "115 um, none at 150 um and above [PROVED, model fitted to simulation].",
            "For partial separation the unfiltered 30 nm LED is brightest (its wider spectrum outweighs "
            "its spectral smear). Clean separation needs a filter of 10 nm or less: at 30 nm the "
            "spectral smear alone exceeds the target [PROVED, model].",
            "Card luminance assumes the image focused on a white card; a scattering fill is 10-100x "
            "dimmer [HEURISTIC].",
        ],
    }


def main():
    OUT.mkdir(exist_ok=True)
    rep = report()
    (OUT / "coherent_build.json").write_text(json.dumps(rep, indent=1))
    for r in rep["frontier_f100"]:
        print(r)
    print(json.dumps(rep["sim_check"], indent=1))


if __name__ == "__main__":
    main()
