"""
Machine-wide rig lock: one process at a time drives the camera + DMD.

An OS byte-range lock (msvcrt on Windows, flock elsewhere) on a fixed file - the SAME mechanism and file
as the swiss-army-scanner's RigLock, so the two programs exclude each other. The OS releases it if the
holding process dies, so there is never a stale lock to break. Never delete the lock file or kill its holder.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from . import config


class RigBusy(RuntimeError):
    """Another program holds the rig. Wait for it; never force it."""


class RigLock:
    def __init__(self, path: Optional[Path] = None, holder: str = config.HOLDER):
        self.path = Path(path) if path else config.LOCK_PATH
        self.info_path = self.path.with_suffix(".info.json")
        self.holder = holder or Path(sys.argv[0]).name
        self._fh = None

    def acquire(self) -> "RigLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fh = open(self.path, "a+b")
        except PermissionError:
            fh = open(self.path, "rb")                 # another user's lock file: still lockable read-only
        try:
            _lock(fh)
        except OSError:
            fh.close()
            raise RigBusy(f"the camera + DMD are in use by another program ({self.describe_holder()}). "
                          "Only one program may drive the rig at a time - wait for it to finish.") from None
        self._fh = fh
        try:
            self.info_path.write_text(json.dumps({"pid": os.getpid(), "holder": self.holder,
                                                  "since": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
        except OSError:
            pass
        return self

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            _unlock(self._fh)
        finally:
            self._fh.close()
            self._fh = None

    def describe_holder(self) -> str:
        try:
            d = json.loads(self.info_path.read_text(encoding="utf-8"))
            return f"pid {d.get('pid')} '{d.get('holder')}' since {d.get('since')}"
        except (OSError, ValueError):
            return "unknown holder"

    @property
    def held(self) -> bool:
        return self._fh is not None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()


def probe(path: Optional[Path] = None) -> tuple:
    """(free, holder) for a status display: the lock is tried and released at once and the holder record is
    not written. A "free" answer can be stale a moment later, so hardware use still goes through acquire()."""
    p = Path(path) if path else config.LOCK_PATH
    try:
        fh = open(p, "rb")                             # read-only: never creates or changes the lock file
    except FileNotFoundError:
        return True, ""                                # nobody has ever locked it on this machine
    except OSError:
        return False, "lock file unreadable"
    try:
        try:
            _lock(fh)
        except OSError:
            return False, RigLock(p).describe_holder()
        _unlock(fh)
        return True, ""
    finally:
        fh.close()


def _lock(fh) -> None:
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover - the bench is Windows
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fh) -> None:
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:  # pragma: no cover
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
