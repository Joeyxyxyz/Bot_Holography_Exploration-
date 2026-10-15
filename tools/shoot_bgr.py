"""
Project BGR frames (as saved by vol2.volplay: f###.png, raw colour) and photograph each; then a GIF.
  python tools/shoot_bgr.py <out_label> <clip_dir> [<clip_dir> ...]
One rig-lock session for all clips. GIFs are built afterwards by make_gif_dir (needs Pillow).
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from rig import bench as vm

EXP = 100000


def main():
    label, dirs = sys.argv[1], [Path(d) for d in sys.argv[2:]]
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_" + label)
    run.mkdir(parents=True)
    lock, sync = vm.open_rig()
    try:
        sync.camera.set_exposure_us(EXP)
        black = sync.shoot(np.zeros((vm.H, vm.W, 3), np.uint8), raw=True).astype(np.float32)
        for d in dirs:
            files = sorted(d.glob("f*.png"))
            shots = []
            for f in files:
                img = cv2.imread(str(f), cv2.IMREAD_COLOR)
                shots.append(np.clip(sync.shoot(img, raw=True).astype(np.float32) - black, 0, None))
            np.savez_compressed(run / f"{d.name}.npz", frames=np.stack(shots).astype(np.float16))
            print(d.name, len(shots), flush=True)
        sync.shoot(np.zeros((vm.H, vm.W), np.uint8))
    finally:
        sync.close()
        lock.release()
    (run / "meta.json").write_text(json.dumps({"clips": [d.name for d in dirs], "exposure_us": EXP,
                                               "note": "background-subtracted camera frames, blue light"}, indent=1))
    print(run)


if __name__ == "__main__":
    main()
