"""
Put a hologram frame on the DMD (HDMI video mode, invert off) and hold it for bench work.

  python holo_show.py allon                      # every mirror ON: a flat field through the stock lens
                                                 # (NOT the T4 lattice test: T4 needs coherent light on the
                                                 #  bare DMD and cannot run through the stock lens)
  python holo_show.py out\\cube3d_diamond_hdmi.png [minutes]
  python holo_show.py out\\glyphX_z400_diamond_hdmi.png

Takes the rig lock (holder dlp_hologram), grabs one camera frame for the record, holds until
the STOP file (repo root) exists or the time runs out, leaves the DMD dark, releases the lock.
The frame must be exactly 1140 x 912 (rows x cols), values 0/255: it is shown 1:1 on the mirrors,
never scaled (HDMIWindow warns if the display is not 912x1140 at (1920, 0)).
cam.png is an intensity projection through the stock lens with incoherent LEDs, NOT a holographic
reconstruction; meta.json next to it says so.
No USB/HID, no LED changes (rig rules).
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rig import bench as vm  # noqa: E402

STOP = Path(__file__).resolve().parents[1] / "STOP"


def load(arg):
    if arg == "allon":
        return np.full((vm.H, vm.W), 255, np.uint8)
    img = cv2.imread(arg, cv2.IMREAD_GRAYSCALE)
    if img is None or img.shape != (vm.H, vm.W):
        raise SystemExit(f"{arg}: need a {vm.H}x{vm.W} grayscale frame, got "
                         f"{None if img is None else img.shape}")
    return np.where(img > 127, 255, 0).astype(np.uint8)


def main():
    frame = load(sys.argv[1])
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    out = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_hold_" + Path(sys.argv[1]).stem)
    out.mkdir(parents=True)
    cv2.imwrite(str(out / "dmd_frame.png"), frame)
    vm.DUTY = 1.0
    lock, sync = vm.open_rig()
    try:
        STOP.unlink(missing_ok=True)  # only now: we hold the rig, so a STOP left over is stale, not another run's
        shot = sync.shoot(frame)
        cv2.imwrite(str(out / "cam.png"), np.clip(shot, 0, 255).astype(np.uint8))
        on = float(frame.mean() / 255)
        src = sys.argv[1] if sys.argv[1] == "allon" else str(Path(sys.argv[1]).resolve())
        (out / "meta.json").write_text(json.dumps({
            "source_frame": src, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "on_fraction": round(on, 4),
            "hold_min": minutes,
            "note": "intensity projection through the stock lens, incoherent LEDs; "
                    "NOT a holographic reconstruction"}, indent=1))
        print(out, f"ON fraction {on:.4f}; holding {minutes} min", flush=True)
        end = time.monotonic() + minutes * 60
        while time.monotonic() < end and not STOP.exists():
            sync.projector.window.hold(0.5)
        sync.shoot(np.zeros((vm.H, vm.W), np.uint8))
    finally:
        sync.close()
        lock.release()
        STOP.unlink(missing_ok=True)
    print("released", flush=True)


if __name__ == "__main__":
    main()
