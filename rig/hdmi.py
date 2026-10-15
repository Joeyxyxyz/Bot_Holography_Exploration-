"""Fullscreen OpenCV window on the DMD's HDMI display. Pumped holds (cv2.waitKey), never a bare sleep:
a window that is not pumped goes stale and the DMD can show an old frame."""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from . import config
from .safety import check_frame, check_hardware_allowed, check_no_usb_hid

RECT_TOL_PX = 2


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
        cv2.moveWindow(self.NAME, *self.monitor_offset)
        cv2.setWindowProperty(self.NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.waitKey(1)
        self._checked = False

    def check_rect(self) -> Optional[bool]:
        try:
            x, y, w, h = (int(v) for v in self._cv2.getWindowImageRect(self.NAME))
        except Exception:  # noqa: BLE001 - old OpenCV / no backend
            return None
        self.rect = (x, y, w, h)
        (ox, oy), (ew, eh) = self.monitor_offset, self.size
        self.rect_ok = all(abs(a - b) <= RECT_TOL_PX for a, b in ((x, ox), (y, oy), (w, ew), (h, eh)))
        if not self.rect_ok:
            print(f"WARNING: DMD window is {w}x{h} at ({x},{y}), expected {ew}x{eh} at ({ox},{oy}). "
                  "Patterns may be scaled or on the wrong monitor (check display settings, 100 % scaling).")
        return self.rect_ok

    def show(self, frame) -> None:
        f = check_frame(frame)
        if f.ndim == 2:
            f = self._cv2.cvtColor(f, self._cv2.COLOR_GRAY2BGR)
        self._cv2.imshow(self.NAME, f)
        self._cv2.waitKey(1)
        if not self._checked:
            self._checked = True
            self.check_rect()

    def hold(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        self._cv2.waitKey(1)
        while time.monotonic() < end:
            self._cv2.waitKey(max(1, min(15, int((end - time.monotonic()) * 1000))))

    def dark(self) -> None:
        self.show(np.zeros((config.DMD_H, config.DMD_W), np.uint8))

    def close(self) -> None:
        try:
            self._cv2.destroyWindow(self.NAME)
        except Exception:  # noqa: BLE001
            pass
