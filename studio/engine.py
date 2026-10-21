"""The studio engine: rig jobs run one at a time on the MAIN thread (so Ctrl+C in the console reaches the player
and the rig is released), previews render on a background thread, and the page reads a state snapshot.

Hardware is only ever touched through vol2.volplay.play(), which opens rig.bench.Bench: shared rig lock, HDMI
window checks, USB/HID guard, DMD blanked and lock released on every exit. Stop = the job's cancel flag (raised
inside the player's progress callback) plus the repo STOP file the player already watches."""
from __future__ import annotations

import collections
import dataclasses
import queue
import threading
import time
import traceback

from rig import config
from rig.lock import RigBusy, probe
from rig.safety import SafetyError, check_hardware_allowed
from vol2 import volplay

from . import catalog, clips

MAX_PLAYLIST_ITEMS = 20
MAX_PLAYLIST_S = 1800.0                # half an hour: no longer than a viewing session holds the rig
GRID_SECONDS = (5.0, 600.0)
GRID_FPS = 10.0                        # a still frame, re-shown 10x a second so the window stays pumped
CLIP_CACHE_BYTES = 600 * 2 ** 20


class Refused(Exception):
    """A request the studio will not run; .status is the HTTP status for the page."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def hardware_allowed() -> bool:
    try:
        check_hardware_allowed()
        return True
    except SafetyError:
        return False


@dataclasses.dataclass
class Item:
    kind: str                          # "scene" or "grid"
    title: str
    seconds: float
    settings: clips.Settings = None


@dataclasses.dataclass
class Job:
    kind: str                          # "play", "playlist" or "grid"
    items: list
    cancel: threading.Event = dataclasses.field(default_factory=threading.Event)


def _seconds(d, lo, hi, default):
    v = d.get("seconds", default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise Refused(f"seconds must be between {lo:g} and {hi:g}", 400)
    return float(v)


def grid_frame():
    """The 2026-10-05 numbered grid (col 1 at DMD 376, row A at 477), white, as Joey called out the case on."""
    from tools.numgrid import WIDE, numgrid
    return numgrid(**WIDE)[0]


class Previewer:
    """Pattern previews and simulated views, rendered one at a time on a daemon thread, newest request first."""

    MAX_QUEUE = 8
    MAX_RESULTS = 96

    def __init__(self):
        self._cv = threading.Condition()
        self._jobs = collections.OrderedDict()           # key -> {"state", "progress", "result", "error"}
        self._queue = collections.deque()
        threading.Thread(target=self._worker, name="studio-previews", daemon=True).start()

    @staticmethod
    def key(kind, s: clips.Settings):
        canon = dataclasses.replace(s, speed=1.0, size=s.size if s.scene in catalog.SIZE_SCENES else 1.0)
        return (kind, canon)

    def request(self, kind, s: clips.Settings) -> dict:
        k = self.key(kind, s)
        with self._cv:
            for other, oj in self._jobs.items():          # someone moved on: drop a render for other settings
                if oj["state"] == "working" and other[1] != k[1]:
                    oj["cancel"].set()
            j = self._jobs.get(k)
            if j is None or j["state"] == "error":
                j = self._jobs[k] = {"state": "queued", "progress": 0.0, "result": None, "error": None,
                                     "cancel": threading.Event()}
            self._jobs.move_to_end(k)
            if j["state"] == "working" and j["cancel"].is_set():
                j["cancel"].clear()                         # asked for again before the worker gave up on it
            if j["state"] == "queued":
                if k in self._queue:
                    self._queue.remove(k)
                self._queue.appendleft(k)                # newest first: people click around
                while len(self._queue) > self.MAX_QUEUE:
                    self._jobs.pop(self._queue.pop(), None)
                self._cv.notify()
            while len(self._jobs) > self.MAX_RESULTS:
                old = next(iter(self._jobs))
                if self._jobs[old]["state"] in ("done", "error"):
                    self._jobs.pop(old)
                else:
                    break
            return {key: v for key, v in j.items() if key != "cancel"}

    def _worker(self):
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait()
                k = self._queue.popleft()
                j = self._jobs.get(k)
                if j is None:
                    continue
                j["state"] = "working"
            kind, s = k

            def progress(i, n, j=j):
                j["progress"] = i / n
            try:
                fn = clips.pattern_preview if kind == "pattern" else clips.simulated_preview
                result = fn(s, cancel=j["cancel"], progress=progress)
                with self._cv:
                    j.update(state="done", progress=1.0, result=result)
            except clips.Cancelled:
                with self._cv:
                    if self._jobs.get(k) is j:
                        self._jobs.pop(k)                   # asked for again later -> starts over
            except Exception as e:  # noqa: BLE001 - shown on the page, printed here
                traceback.print_exc()
                with self._cv:
                    j.update(state="error", error=f"{type(e).__name__}: {e}")


class Studio:
    def __init__(self):
        self.hardware = hardware_allowed()
        self.previews = Previewer()
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._job = None
        self._clips = collections.OrderedDict()
        self._log = collections.deque(maxlen=40)
        self._state = {"activity": "idle", "now": None, "last": None}
        self._rig = {"free": None, "holder": "", "checked": None}
        self.check_rig()
        self.log("Studio started" + ("" if self.hardware else " in preview-only mode (DLP_NO_HARDWARE is set)"))

    # ---------------------------------------------------------------- called from HTTP threads
    def log(self, msg):
        with self._lock:
            self._log.append({"t": time.strftime("%H:%M:%S"), "msg": msg})
        print(f"[studio] {msg}", flush=True)

    def check_rig(self):
        if not self.hardware:                            # preview only: leave the shared lock file alone
            return dict(self._rig)
        free, holder = probe()
        with self._lock:
            self._rig = {"free": free, "holder": holder, "checked": time.strftime("%H:%M:%S")}
        return dict(self._rig)

    def snapshot(self) -> dict:
        with self._lock:
            return {"hardware": self.hardware, "activity": self._state["activity"], "now": self._state["now"],
                    "last": self._state["last"], "rig": dict(self._rig), "log": list(self._log),
                    "busy": self._job is not None}

    def submit_play(self, body) -> dict:
        s = self._settings(body)
        sec = _seconds(body, *clips.LIMITS["seconds"], clips.DEFAULTS["seconds"])
        return self._submit(Job("play", [Item("scene", self._title(s), sec, s)]))

    def submit_playlist(self, body) -> dict:
        items = body.get("items") if isinstance(body, dict) else None
        if not isinstance(items, list) or not items:
            raise Refused("the playlist is empty", 400)
        if len(items) > MAX_PLAYLIST_ITEMS:
            raise Refused(f"at most {MAX_PLAYLIST_ITEMS} scenes in a playlist", 400)
        out = []
        for it in items:
            s = self._settings(it)
            out.append(Item("scene", self._title(s), _seconds(it, *clips.LIMITS["seconds"], 20.0), s))
        if sum(i.seconds for i in out) > MAX_PLAYLIST_S:
            raise Refused(f"a playlist may run at most {MAX_PLAYLIST_S / 60:g} minutes", 400)
        return self._submit(Job("playlist", out))

    def submit_grid(self, body) -> dict:
        sec = _seconds(body if isinstance(body, dict) else {}, *GRID_SECONDS, 60.0)
        return self._submit(Job("grid", [Item("grid", "Numbered grid (case check)", sec)]))

    def stop(self) -> dict:
        """Stop whatever runs: this studio's job, and (through the STOP file) any player started from this repo."""
        with self._lock:
            job = self._job
        if job is not None:
            job.cancel.set()
        try:
            config.STOP.touch()
        except OSError as e:
            self.log(f"could not create the STOP file: {e}")
        self.log("STOP pressed")
        return {"stopping": job is not None}

    def _settings(self, d) -> clips.Settings:
        try:
            return clips.Settings.from_dict(d)
        except ValueError as e:
            raise Refused(str(e), 400) from None

    @staticmethod
    def _title(s):
        return catalog.scenes()[s.scene]["title"]

    def _submit(self, job: Job) -> dict:
        if not self.hardware:
            raise Refused("Preview only: DLP_NO_HARDWARE is set, so this studio may not drive the projector.")
        with self._lock:
            if self._job is not None:
                raise Refused("Something is already playing. Press STOP first.")
            self._job = job
            self._state["activity"] = "queued"
            self._state["now"] = {"kind": job.kind, "title": job.items[0].title, "index": 1, "count": len(job.items)}
        self._queue.put(job)
        self.log(f"queued: {', '.join(i.title for i in job.items)}")
        return {"queued": True}

    # ---------------------------------------------------------------- main thread
    def run_forever(self, until=None):
        """Run rig jobs until `until` (an Event) is set. Ctrl+C raises KeyboardInterrupt here, inside the player,
        so the Bench blanks the DMD and releases the lock on the way out."""
        while until is None or not until.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._run(job)

    def _set(self, activity=None, **now):
        with self._lock:
            if activity is not None:
                self._state["activity"] = activity
            if now:
                self._state["now"] = {**(self._state["now"] or {}), **now}

    def _finish(self, job, last):
        with self._lock:
            self._state.update(activity="idle", now=None, last={**last, "t": time.strftime("%H:%M:%S")})
            self._job = None
        self.check_rig()

    def _run(self, job: Job):
        results = []
        try:
            free, holder = probe()
            if not free:
                raise RigBusy(f"the camera + DMD are in use by another program ({holder}).")
            for n, item in enumerate(job.items, 1):
                if job.cancel.is_set() or (n > 1 and config.STOPALL.exists()):
                    break
                self._set("preparing", title=item.title, index=n, count=len(job.items), seconds=item.seconds,
                          render=0.0, elapsed=0.0, shown=0, dropped=0)
                if item.kind == "grid":
                    frames, fps = [grid_frame()], GRID_FPS
                else:
                    frames = self._clip(item, job)
                    fps = frames.fps
                self._set("holding" if item.kind == "grid" else "playing", fps=round(fps, 1))
                self.log(f"playing {item.title} for {item.seconds:g} s")

                def progress(shown, dropped, elapsed):
                    if job.cancel.is_set():
                        raise clips.Cancelled()
                    self._set(shown=shown, dropped=dropped, elapsed=round(elapsed, 1))
                res = volplay.play(frames, fps, item.seconds, progress=progress)
                results.append({"title": item.title, **res})
                self.log(f"done {item.title}: {res['achieved_fps']} fps, {res['dropped']} late frames")
            stopped = job.cancel.is_set()
            self._finish(job, {"status": "stopped" if stopped else "done", "results": results})
            if stopped:
                self.log("stopped")
        except clips.Cancelled:
            self._finish(job, {"status": "stopped", "results": results})
            self.log("stopped")
        except RigBusy as e:
            self._finish(job, {"status": "busy", "message": str(e), "results": results})
            self.log(f"rig busy: {e}")
        except SafetyError as e:
            self._finish(job, {"status": "refused", "message": str(e), "results": results})
            self.log(f"refused by a safety check: {e}")
        except KeyboardInterrupt:
            self._finish(job, {"status": "stopped", "message": "Ctrl+C", "results": results})
            raise
        except Exception as e:  # noqa: BLE001 - reported on the page; the Bench has already cleaned up
            traceback.print_exc()
            self._finish(job, {"status": "error", "message": f"{type(e).__name__}: {e}", "results": results})
            self.log(f"error: {type(e).__name__}: {e}")

    def _clip(self, item: Item, job: Job) -> clips.Clip:
        key = (item.settings, clips.clip_timing(item.settings, item.seconds))
        clip = self._clips.get(key)
        if clip is not None:
            self._clips.move_to_end(key)
            return clip

        def progress(i, n):
            self._set(render=round(i / n, 3))
        clip = clips.render_clip(item.settings, item.seconds, cancel=job.cancel, progress=progress)
        self._clips[key] = clip
        while sum(c.nbytes for c in self._clips.values()) > CLIP_CACHE_BYTES and len(self._clips) > 1:
            self._clips.popitem(last=False)
        return clip
