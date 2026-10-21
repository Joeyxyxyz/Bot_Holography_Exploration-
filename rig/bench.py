"""
The bench as one object: lock -> HDMI window -> camera, released in reverse on every exit path.

    from rig import bench
    with bench.Bench(exposure_us=66667) as b:          # takes the rig lock (RigBusy if held)
        img = b.shoot(frame)                             # project, pumped hold, flush, average grabs
    # lock released, DMD dark, camera closed

Projection only (no camera): Bench(camera=False). Frames: mono 0/255 (shown with optional duty/invert) or
BGR uint8 shown raw (colour = which LED sub-frames the mirrors are on in; LED currents are untouched).
The legacy helpers (H, W, OUT, open_rig) keep the scripts in tools/ and vol2/ working unchanged.
"""
from __future__ import annotations

import numpy as np

from . import config
from .hdmi import HDMIWindow
from .lock import RigLock
from .safety import check_frame, check_hardware_allowed, check_no_usb_hid

H, W = config.DMD_H, config.DMD_W
OUT = config.RUNS
HOLDER = config.HOLDER
EXPOSURE_US = config.EXPOSURE_US
AVERAGE = config.AVERAGE
DUTY = 1.0


class _Projector:
    def __init__(self, window: HDMIWindow, duty=1.0, invert=False, min_hold_s=config.MIN_HOLD_S):
        self.window, self.duty, self.invert, self.min_hold_s = window, duty, invert, min_hold_s

    def prepare(self, pattern):
        p = check_frame(pattern)
        if p.ndim == 3:                                   # colour frames are shown as given
            return p
        if self.duty != 1.0:
            p = (p.astype(np.float32) * self.duty).astype(np.uint8)
        return 255 - p if self.invert else p

    def project(self, pattern, raw=False):
        check_no_usb_hid()
        shown = check_frame(pattern) if raw else self.prepare(pattern)
        self.window.show(shown)
        self.window.show(shown)                           # the DMD shows HDMI one frame behind
        self.window.hold(self.min_hold_s)

    def close(self):
        self.window.close()


class Bench:
    def __init__(self, exposure_us=config.EXPOSURE_US, average=config.AVERAGE, camera=True, duty=1.0,
                 holder=config.HOLDER, min_hold_s=config.MIN_HOLD_S):
        check_hardware_allowed()                          # refuse before touching the lock
        check_no_usb_hid()
        self.lock = RigLock(holder=holder).acquire()
        self.window = self.camera = None
        try:
            self.window = HDMIWindow()
            self.projector = _Projector(self.window, duty=duty, min_hold_s=min_hold_s)
            if camera:
                from .camera import Camera
                self.camera = Camera(exposure_us)
            self.average = average
        except BaseException:
            self.close()
            raise

    def shoot(self, pattern, raw=False):
        self.projector.project(pattern, raw=raw)
        if self.camera is None:
            return None
        for _ in range(config.FLUSH):
            self.camera.flush()
        acc = self.camera.grab().astype(np.float32)
        for _ in range(self.average - 1):
            acc += self.camera.grab().astype(np.float32)
        return acc / self.average

    def close(self):
        """DMD dark -> window closed -> camera closed -> lock released. Each step runs even if an earlier one
        fails, so the lock is never released with the camera still open. Safe to call more than once."""
        window, camera, self.window, self.camera = self.window, self.camera, None, None
        try:
            try:
                if window is not None:
                    try:
                        window.dark()
                    finally:
                        window.close()
            finally:
                if camera is not None:
                    camera.close()
        finally:
            self.lock.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------- legacy interface used by the scripts
class _Sync:
    """(lock, sync) pair as returned by open_rig(): sync.shoot / sync.camera / sync.projector.window / close."""

    def __init__(self, b: Bench):
        self._b = b
        self.camera = b.camera
        self.projector = b.projector

    def shoot(self, pattern, raw=False):
        return self._b.shoot(pattern, raw=raw)

    def close(self):
        """Full Bench clean-up, lock included; the caller's lock.release() afterwards is then a no-op."""
        self._b.close()


def open_rig():
    b = Bench(exposure_us=EXPOSURE_US, average=AVERAGE, duty=DUTY)
    return b.lock, _Sync(b)
