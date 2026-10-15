"""
Project a list of 1140x912 frames and photograph each (rig lock held for the whole set, released at the end).
Exposures are whole multiples of the 16667 us HDMI frame (no PWM flicker).

  python tools/shoot_set.py <label> <frame.png> [<frame.png> ...]
Writes runs/<ts>_<label>/cam_<name>_<exp>us.png and raw.npz; the DMD is left dark.
"""
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from rig import bench as vm

# SHOOT_COLOR=blue|green|red|white (default white); blue excites the fluorescein fill
COLOR = os.environ.get("SHOOT_COLOR", "white").lower()
BGR = {"blue": (1, 0, 0), "green": (0, 1, 0), "red": (0, 0, 1), "white": (1, 1, 1)}
# whole multiples of 16667 us; override with e.g. SHOOT_EXP=200000,500000
EXPOSURES = tuple(int(x) for x in os.environ.get("SHOOT_EXP", "16667,66667").split(","))


def load(p):
    if p == "black":
        return "black", np.zeros((vm.H, vm.W), np.uint8)
    img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if img is None or img.shape != (vm.H, vm.W):
        raise SystemExit(f"{p}: need {vm.H}x{vm.W}")
    return Path(p).parent.name + "__" + Path(p).stem, np.where(img > 127, 255, 0).astype(np.uint8)


def main():
    label, paths = sys.argv[1], sys.argv[2:]
    frames = [load(p) for p in paths]
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_" + label)
    run.mkdir(parents=True)
    vm.DUTY = 1.0
    lock, sync = vm.open_rig()
    shots = {}
    try:
        for exp in EXPOSURES:
            sync.camera.set_exposure_us(exp)
            for name, f in frames:
                if COLOR == "white":
                    img = sync.shoot(f).astype(np.float32)
                else:                                    # raw BGR: only that LED's sub-frames, no LED change
                    b, g, r = BGR[COLOR]
                    img = sync.shoot(np.dstack([f * b, f * g, f * r]).astype(np.uint8), raw=True).astype(np.float32)
                key = f"{name}_{exp}us"
                shots[key] = img
                cv2.imwrite(str(run / f"cam_{key}.png"), np.clip(img, 0, 255).astype(np.uint8))
                print(f"  {key:60s} mean {img.mean():7.2f} max {img.max():5.0f}", flush=True)
        sync.shoot(np.zeros((vm.H, vm.W), np.uint8))
    finally:
        sync.close()
        lock.release()
    np.savez_compressed(run / "raw.npz", **{k: v.astype(np.float16) for k, v in shots.items()})
    (run / "frames.txt").write_text("\n".join(paths))
    print(run)


if __name__ == "__main__":
    main()
