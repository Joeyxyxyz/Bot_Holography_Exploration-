"""Machine-safety guards checked before and during any hardware use (see SAFETY.md)."""
from __future__ import annotations

import os
import sys

import numpy as np

from . import config

# Modules that could talk to the DLPC350 over USB/HID. This package never imports them; if anything in
# the process has, refuse to drive the rig (a USB mode/source command while projecting can drop the DMD
# into a test pattern, and LED commands could exceed the unit's current limits).
FORBIDDEN_MODULES = ("hid", "hidapi", "usb", "usb.core", "pyusb", "pywinusb", "dmd_control")


class SafetyError(RuntimeError):
    pass


def check_hardware_allowed() -> None:
    """DLP_NO_HARDWARE=1 (set by the tests, CI and cloud sessions) forbids opening the DMD window or camera."""
    if os.environ.get("DLP_NO_HARDWARE", "").strip() not in ("", "0"):
        raise SafetyError("DLP_NO_HARDWARE is set: this process may not open the DMD window or the camera.")


def check_no_usb_hid() -> None:
    loaded = [m for m in FORBIDDEN_MODULES if m in sys.modules]
    if loaded:
        raise SafetyError(f"USB/HID modules loaded in this process ({', '.join(loaded)}): the rig is driven over "
                          "HDMI only. Run hardware scripts in a clean process.")


def check_frame(frame) -> np.ndarray:
    """Exact DMD size and uint8 only: frames are shown 1:1 on the mirrors, never scaled."""
    f = np.asarray(frame)
    if f.dtype != np.uint8:
        raise SafetyError(f"frame dtype {f.dtype}, need uint8")
    if f.shape[:2] != (config.DMD_H, config.DMD_W) or f.ndim not in (2, 3) or (f.ndim == 3 and f.shape[2] != 3):
        raise SafetyError(f"frame shape {f.shape}, need ({config.DMD_H}, {config.DMD_W}) or "
                          f"({config.DMD_H}, {config.DMD_W}, 3)")
    return f
