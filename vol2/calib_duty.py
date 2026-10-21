"""
Measure the projector's duty curve in the glycerin and the achievable HDMI refresh rate.

  python -m vol2.calib_duty duty     # blue level 0..255 on a plane-B band -> camera glow; fits glow ~ (v/255)^gamma
  python -m vol2.calib_duty analyse <run>   # offline: re-derive duty_roi.json from a run's raw.npz
  python -m vol2.calib_duty rate     # pushes alternating frames as fast as possible (no camera), measures fps
Takes the rig lock; HDMI video mode; raw BGR (blue only); no LED change.
duty.json sums the whole frame (clipped at 0, so noise biases the low levels); duty_roi.json (what the player
reads) sums only the pixels that glow at 255 (> 8 sigma of the noise), unclipped.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rig import bench as vm  # noqa: E402

H, W = 1140, 912
BAND = (slice(900, 1050), slice(700, 740))          # plane-B band inside the liquid (case_fit_tank_v4)
LEVELS = [0, 16, 32, 48, 64, 96, 128, 160, 192, 224, 255]


def blue(level, band=BAND):
    f = np.zeros((H, W, 3), np.uint8)
    f[band[0], band[1], 0] = level
    return f


def duty(exp_us=66667):
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_duty")
    run.mkdir(parents=True)
    lock, sync = vm.open_rig()
    shots = {}
    try:
        sync.camera.set_exposure_us(exp_us)
        for rep in range(2):
            for v in LEVELS:
                img = sync.shoot(blue(v), raw=True).astype(np.float32)
                shots.setdefault(v, []).append(img)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close()
        lock.release()
    mean = {v: np.mean(shots[v], axis=0) for v in LEVELS}
    black = mean[0]
    sig = {v: float(np.clip(mean[v] - black, 0, None).sum()) for v in LEVELS}
    top = sig[255] or 1.0
    rel = {v: sig[v] / top for v in LEVELS}
    vs = np.array([v for v in LEVELS if v > 0], float) / 255
    ys = np.array([rel[v] for v in LEVELS if v > 0])
    ok = ys > 0.003
    gamma = float(np.polyfit(np.log(vs[ok]), np.log(ys[ok]), 1)[0])
    rep = {"exposure_us": exp_us, "relative_glow": rel, "gamma_fit": gamma,
           "note": "glow ~ (v/255)^gamma; duty d -> blue level 255 * d^(1/gamma)"}
    (run / "duty.json").write_text(json.dumps(rep, indent=1))
    np.savez_compressed(run / "raw.npz", **{f"v{v}": mean[v].astype(np.float16) for v in LEVELS})
    print(json.dumps(rep, indent=1))
    analyse(run)
    return rep


def roi_curve(mean):
    """Relative glow summed over the pixels that glow at 255 (> 8 sigma of the noise), unclipped.
    mean: {level: mean camera image}. The noise sigma is taken where level 255 adds < 2 DN."""
    b = mean[0].astype(np.float32)
    d255 = mean[255].astype(np.float32) - b
    quiet = d255 < 2
    noise = float(np.std((mean[16].astype(np.float32) - b)[quiet])) if quiet.any() else 1.0
    mask = d255 > max(8 * noise, 6)
    sig = {v: float((mean[v].astype(np.float32) - b)[mask].sum()) for v in LEVELS}
    rel = {v: sig[v] / (sig[255] or 1.0) for v in LEVELS}
    vs = np.array(LEVELS[1:], float) / 255
    ys = np.array([rel[v] for v in LEVELS[1:]])
    ok = ys > 0.01
    gamma = float(np.polyfit(np.log(vs[ok]), np.log(ys[ok]), 1)[0])
    return {"relative_glow": rel, "gamma_fit": gamma, "mask_px": int(mask.sum()), "noise_dn": noise,
            "method": "ROI = pixels > 8 sigma at 255, unclipped"}


def analyse(run):
    run = Path(run)
    z = np.load(run / "raw.npz")
    rep = roi_curve({v: z[f"v{v}"] for v in LEVELS})
    (run / "duty_roi.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


def rate(seconds=6.0):
    from rig.bench import Bench
    with Bench(camera=False, min_hold_s=0.0) as b:     # DMD dark and lock released on any exit
        frames = [blue(255, (slice(900, 1050), slice(700 + 10 * k, 710 + 10 * k))) for k in range(4)]
        n, t0 = 0, time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            b.window.show(frames[n % 4])
            n += 1
        fps = n / (time.perf_counter() - t0)
    print(json.dumps({"frames": n, "seconds": seconds, "fps_window_loop": round(fps, 1),
                      "note": "upper bound of show() calls; the DMD itself refreshes at the 60 Hz HDMI rate"}))


if __name__ == "__main__":
    if sys.argv[1] == "analyse":
        analyse(sys.argv[2])
    else:
        {"duty": duty, "rate": rate}[sys.argv[1]]()
