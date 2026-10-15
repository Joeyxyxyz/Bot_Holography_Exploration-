"""Bench configuration. Override with environment variables; nothing here is user-specific."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# DMD as an HDMI monitor (DLP LightCrafter 4500 native video mode)
DMD_W, DMD_H = 912, 1140
_off = os.environ.get("DLP_MONITOR_OFFSET", "1920,0").split(",")
MONITOR_OFFSET = (int(_off[0]), int(_off[1]))           # desktop position of the DMD display

# Camera defaults: a whole number of 60 Hz HDMI frames avoids PWM flicker
EXPOSURE_US = int(os.environ.get("DLP_EXPOSURE_US", "16667"))
AVERAGE = 2
FLUSH = 4
MIN_HOLD_S = 0.35            # pumped hold after each pattern before the camera grabs (stale-frame guard)

# Shared machine-wide rig lock. The default is the swiss-army-scanner's lock file so both tools exclude
# each other; change it only if no other program on this machine drives the same camera / DMD.
_pd = os.environ.get("PROGRAMDATA")
DEFAULT_LOCK = Path(_pd) / "swiss_army_scanner" / "rig.lock" if _pd else \
    Path(tempfile.gettempdir()) / "swiss_army_scanner_rig.lock"
LOCK_PATH = Path(os.environ.get("DLP_RIG_LOCK", str(DEFAULT_LOCK)))
HOLDER = "dlp_hologram"

# Where captures go (git-ignored)
RUNS = Path(os.environ.get("DLP_RUNS", str(REPO / "runs")))

# Stop files: STOP ends the current playback / hold at once; STOPALL ends a playlist
STOP = REPO / "STOP"
STOPALL = REPO / "STOPALL"
