"""
Same cube hologram (cube3d_diamond_hdmi.png), reconstructed under partially coherent LED light.

Temporal coherence: LED spectrum sampled (Gaussian, FWHM given), intensities summed per plane.
  (Fresnel focus scales ~1/lambda and the +1-order offset ~lambda -> axial + lateral chromatic smear.)
Spatial coherence: source of diameter d behind a collimator of focal length f gives plane waves
  within half-angle theta = d / (2 f); each tilt shifts the reconstruction by z*theta, so the image
  is convolved with a disk of radius z*theta (paraxial shift invariance).
Throughput is reported relative to the bare LED (die ~1 mm imaged 1:1 on the pinhole, Gaussian spectrum).
All [PROVED] as computations of this model; nothing measured. Laser row is the reference.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import fresnel_cube as fc

OUT = Path(__file__).parent / "out"
LAM0 = 532e-9                      # design wavelength
DIE_MM = 1.0
F_COL_MM = 100.0
CONFIGS = [  # name, FWHM nm (0 = laser), source diameter mm
    ("laser_532", 0.0, 0.0),
    ("led_30nm_pin75um", 30.0, 0.075),
    ("led_10nm_pin75um", 10.0, 0.075),
    ("led_3nm_pin75um", 3.0, 0.075),
    ("led_10nm_pin200um", 10.0, 0.200),
    ("led_10nm_pin500um", 10.0, 0.500),
    ("led_10nm_bare_die_1mm", 10.0, 1.000),
]
LED_FWHM_NM = 30.0                 # unfiltered green LED (package LED_GREEN bandwidth)
HALF_MM, WPX = 6.0, 256


def spectrum(fwhm_nm, n=7):
    if fwhm_nm == 0:
        return [LAM0], [1.0]
    s = fwhm_nm / 2.3548
    lams = LAM0 + np.linspace(-1.5, 1.5, n) * fwhm_nm * 1e-9
    w = np.exp(-0.5 * ((lams - LAM0) / (s * 1e-9)) ** 2)
    return list(lams), list(w / w.sum())


def disk(r_px):
    if r_px < 0.5:
        return None
    R = int(np.ceil(r_px))
    y, x = np.mgrid[-R:R + 1, -R:R + 1]
    k = (x * x + y * y <= r_px * r_px).astype(np.float32)
    return k / k.sum()


def main():
    M = (cv2.imread(str(OUT / "cube3d_diamond_hdmi.png"), 0) > 0).astype(np.float32)
    U = fc.raster_mirrors(M, "diamond")
    segs = fc.cube_segments()
    fc.LAM = LAM0
    tg = [fc.window(fc.render(segs[k], z, shift_mm=-(fc.x_off(z) - fc.x_off(fc.ZS[1])) * 1e3), z, 0.0)
          for k, z in enumerate(fc.ZS)]
    xc = fc.x_off(fc.ZS[1])        # design-wavelength image centre (m)
    cache = {}
    rep = {"die_mm": DIE_MM, "f_col_mm": F_COL_MM, "configs": {}}
    rows = []
    for name, fwhm, d_mm in CONFIGS:
        lams, ws = spectrum(fwhm)
        key = fwhm
        if key not in cache:
            planes = []
            for z in fc.ZS:
                acc = np.zeros((WPX, WPX), np.float32)
                for lam, w in zip(lams, ws):
                    fc.LAM = lam
                    Uz, _, _ = fc.fresnel_fwd(U, z)
                    acc += w * fc.window(np.abs(Uz) ** 2, z, xc, HALF_MM, WPX)
                planes.append(acc)
            fc.LAM = LAM0
            cache[key] = planes
        theta = d_mm * 1e-3 / (2 * F_COL_MM * 1e-3)
        out = []
        for z, P in zip(fc.ZS, cache[key]):
            k = disk(z * theta / (2 * HALF_MM * 1e-3 / WPX))
            out.append(P if k is None else cv2.filter2D(P, -1, k, borderType=cv2.BORDER_CONSTANT))
        C = [[round(float(np.corrcoef(p.ravel(), t.ravel())[0, 1]), 3) for t in tg] for p in out]
        diag = float(np.mean([C[i][i] for i in range(3)]))
        off = float(np.mean([C[i][j] for i in range(3) for j in range(3) if i != j]))
        thr = (min(1.0, (d_mm / DIE_MM) ** 2) if d_mm else None)
        spec = (min(1.0, fwhm / LED_FWHM_NM) if fwhm else None)
        rep["configs"][name] = {"corr": C, "diag_mean": round(diag, 3), "offdiag_mean": round(off, 3),
                                "source_half_angle_mrad": round(theta * 1e3, 3),
                                "blur_radius_mm_at_zmid": round(fc.ZS[1] * theta * 1e3, 3),
                                "throughput_vs_bare_led": (round(thr * spec, 5) if thr and spec else None)}
        print(name, rep["configs"][name], flush=True)
        rows.append(np.vstack([(np.clip(p / max(p.max(), 1e-30), 0, 1) ** 0.5 * 255).astype(np.uint8)
                               for p in out]))
    cv2.imwrite(str(OUT / "led_study_montage.png"), np.hstack(rows))
    (OUT / "led_study.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
