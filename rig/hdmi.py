"""Fullscreen OpenCV window on the DMD's HDMI display. Pumped holds (cv2.waitKey), never a bare sleep:
a window that is not pumped goes stale and the DMD can show an old frame.

The window paints black and checks its own position and size before anything else is shown: if it is not
exactly the DMD display (wrong monitor, display scaling, wrong resolution), it refuses (SafetyError) rather
than project scaled patterns."""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from . import config
from .safety import SafetyError, check_frame, check_hardware_allowed, check_no_usb_hid

RECT_TOL_PX = 2               # window rect vs the expected DMD display, per edge (same as the scanner)
DARK_HOLD_S = 0.05            # >= 2 HDMI frames: the DMD shows HDMI one frame behind


class HDMIWindow:
    NAME = "dlp-hologram-dmd"

    def __init__(self, monitor_offset=config.MONITOR_OFFSET, size=(config.DMD_W, config.DMD_H)):
        check_hardware_allowed()
        check_no_usb_hid()
        import cv2
        self._cv2 = cv2
        self.size = tuple(size)
        self.monitor_offset = tuple(monitor_offset)
        self.rect: Optional[tuple] = None
        self.rect_ok: Optional[bool] = None
        cv2.namedWindow(self.NAME, cv2.WINDOW_NORMAL)
        try:
            cv2.moveWindow(self.NAME, *self.monitor_offset)
            cv2.setWindowProperty(self.NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            black = np.zeros((self.size[1], self.size[0], 3), np.uint8)
            self._paint(black)
            self._paint(black)
            if self.check_rect() is False:
                x, y, w, h = self.rect
                (ox, oy), (ew, eh) = self.monitor_offset, self.size
                raise SafetyError(f"DMD window is {w}x{h} at ({x},{y}), expected {ew}x{eh} at ({ox},{oy}): patterns "
                                  "would be scaled or on the wrong monitor. Check the display settings (DMD display "
                                  "912x1140, 100 % scaling) or DLP_MONITOR_OFFSET.")
            if self.rect_ok is None:
                print("WARNING: could not read the DMD window rect; check by eye that patterns are not scaled.")
        except BaseException:
            self.close()
            raise

    def check_rect(self) -> Optional[bool]:
        try:
            x, y, w, h = (int(v) for v in self._cv2.getWindowImageRect(self.NAME))
        except Exception:  # noqa: BLE001 - old OpenCV / no backend
            self.rect = self.rect_ok = None
            return None
        self.rect = (x, y, w, h)
        (ox, oy), (ew, eh) = self.monitor_offset, self.size
        self.rect_ok = all(abs(a - b) <= RECT_TOL_PX for a, b in ((x, ox), (y, oy), (w, ew), (h, eh)))
        return self.rect_ok

    def _paint(self, f) -> None:
        self._cv2.imshow(self.NAME, f)
        self._cv2.waitKey(1)

    def show(self, frame) -> None:
        check_no_usb_hid()                                # every frame, not only when the rig opens
        f = check_frame(frame)
        if f.ndim == 2:
            f = self._cv2.cvtColor(f, self._cv2.COLOR_GRAY2BGR)
        self._paint(f)

    def hold(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        self._cv2.waitKey(1)
        while time.monotonic() < end:
            self._cv2.waitKey(max(1, min(15, int((end - time.monotonic()) * 1000))))

    def dark(self) -> None:
        black = np.zeros((config.DMD_H, config.DMD_W), np.uint8)
        self.show(black)
        self.show(black)
        self.hold(DARK_HOLD_S)

    def close(self) -> None:
        try:
            self._cv2.destroyWindow(self.NAME)
            self._cv2.waitKey(1)
        except Exception:  # noqa: BLE001
            pass
