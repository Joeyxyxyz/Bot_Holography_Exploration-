"""
Projection only (no camera): cycle frames on the DMD for viewing.

  python tools/play_loop.py <seconds_per_frame> <loops> <frame.png> [...]
  set PLAY_COLOR=blue|green|red|white (default white): a colour frame lights only that LED's sub-frames
  over HDMI (raw BGR; LED currents are not changed). Blue excites fluorescein.
Frames must be mono 0/255, exactly 1140 x 912 (use vol2.volplay for graded / BGR frames).
Takes the rig lock, holds with pumped waits, stops early when the STOP file exists, leaves the DMD dark,
releases the lock.
"""
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from rig import config  # noqa: E402
from rig.bench import Bench  # noqa: E402

COLOR = os.environ.get("PLAY_COLOR", "white").lower()
BGR = {"blue": (1, 0, 0), "green": (0, 1, 0), "red": (0, 0, 1), "white": (1, 1, 1)}


def colourise(f):
    b, g, r = BGR[COLOR]
    return np.dstack([f * b, f * g, f * r]).astype(np.uint8)


def main():
    per, loops, paths = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
    frames = []
    for p in paths:
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None or img.shape != (config.DMD_H, config.DMD_W):
            raise SystemExit(f"{p}: need a {config.DMD_H}x{config.DMD_W} mono frame")
        frames.append((Path(p).stem, np.where(img > 127, 255, 0).astype(np.uint8)))
    with Bench(camera=False, min_hold_s=min(config.MIN_HOLD_S, per)) as b:
        config.STOP.unlink(missing_ok=True)           # we hold the rig: a leftover STOP is stale
        try:
            for k in range(loops):
                for name, f in frames:
                    if config.STOP.exists():
                        raise KeyboardInterrupt
                    print(f"loop {k + 1}/{loops}  {name}", flush=True)
                    b.shoot(f if COLOR == "white" else colourise(f), raw=COLOR != "white")
                    end = time.monotonic() + max(0.0, per - min(config.MIN_HOLD_S, per))
                    while time.monotonic() < end:
                        if config.STOP.exists():
                            raise KeyboardInterrupt
                        b.window.hold(min(0.5, max(end - time.monotonic(), 0.0)))
        except KeyboardInterrupt:
            print("stopped", flush=True)
        finally:
            config.STOP.unlink(missing_ok=True)
    print("released", flush=True)


if __name__ == "__main__":
    main()
