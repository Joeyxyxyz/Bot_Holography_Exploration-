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

# Shared machine-wide rig lock: the swiss-army-scanner's lock file, so the two tools exclude each other.
# Deliberately not configurable: moving it would silently end that exclusion. (Tests patch LOCK_PATH.)
def default_lock(programdata=None) -> Path:
    pd = programdata if programdata is not None else os.environ.get("PROGRAMDATA")
    return Path(pd) / "swiss_army_scanner" / "rig.lock" if pd else \
        Path(tempfile.gettempdir()) / "swiss_army_scanner_rig.lock"


LOCK_PATH = default_lock()
HOLDER = "dlp_hologram"

# Where captures go (git-ignored)
RUNS = Path(os.environ.get("DLP_RUNS", str(REPO / "runs")))

# Stop files: STOP ends the current playback / hold at once; STOPALL ends a playlist
STOP = REPO / "STOP"
STOPALL = REPO / "STOPALL"
