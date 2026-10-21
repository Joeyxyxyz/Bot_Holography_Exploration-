"""Rendering for the studio (no hardware): playable clips with the people-facing settings, preview sprites of the
mirror pattern, and a simulated view of the glow in the case.

Settings people can change: speed (time scale), brightness (duty gain, applied before the measured duty curve,
so very low values fall into its dead zone), size (solid shapes only), which faces light (A+B or B only) and the
absorption length L [HEURISTIC, the player's default 30 mm]. The frame rate is 60 Hz (the HDMI rate); a loop
longer than MAX_FRAMES frames is rendered at a lower rate and pushed at that rate."""
from __future__ import annotations

import base64
import collections
import math
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from vol2 import simulate, volplay

H, W = volplay.H, volplay.W
FPS = 60.0
MAX_FRAMES = 600                       # one loop at most 10 s of 60 Hz frames (memory and render time)
CASE_JSON = volplay.ROOT / "configs" / "case_fit_tank_v4.json"
CASE_MAP = volplay.ROOT / "configs" / "case_map_tank_v2.json"

LIMITS = {"seconds": (1.0, 600.0), "speed": (0.25, 2.0), "brightness": (0.3, 1.0), "size": (0.5, 1.5),
          "L": (10.0, 100.0)}
DEFAULTS = {"seconds": 30.0, "speed": 1.0, "brightness": 1.0, "size": 1.0, "mode": "ab", "L": 30.0}
MODES = ("ab", "b")


class Cancelled(Exception):
    """Rendering or playback was stopped by the user."""


def _num(d, k):
    v = d.get(k, DEFAULTS[k])
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{k} must be a number")
    lo, hi = LIMITS[k]
    try:
        ok = math.isfinite(v) and lo <= v <= hi
    except OverflowError:                              # a huge integer
        ok = False
    if not ok:
        raise ValueError(f"{k} must be between {lo:g} and {hi:g}")
    return float(v)


@dataclass(frozen=True)
class Settings:
    scene: str
    speed: float = 1.0
    brightness: float = 1.0
    size: float = 1.0
    mode: str = "ab"
    L: float = 30.0

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        """Validated settings from a request body or query. Raises ValueError with a message for people."""
        if not isinstance(d, dict):
            raise ValueError("settings must be an object")
        scene = d.get("scene")
        if scene not in volplay.SCENES:
            raise ValueError("unknown scene")
        mode = d.get("mode", DEFAULTS["mode"])
        if mode not in MODES:
            raise ValueError("mode must be 'ab' or 'b'")
        return cls(scene, _num(d, "speed"), _num(d, "brightness"), _num(d, "size"), mode, _num(d, "L"))

    def shape_key(self):
        """What changes the light pattern (not the playback speed)."""
        from .catalog import SIZE_SCENES
        return (self.scene, self.mode, round(self.L, 2), round(self.size, 3) if self.scene in SIZE_SCENES else 1.0)


# ---------------------------------------------------------------- shared, per-thread model objects
_local = threading.local()
_lut_lock = threading.Lock()
_lut = None


def duty_lut():
    """The player's duty curve: the newest complete bench run, else the bundled 2026-10-05 curve."""
    global _lut
    with _lut_lock:
        if _lut is None:
            _lut = volplay.load_duty_lut()
        return _lut


VOLUMES_PER_THREAD = 3


def volume(mode="ab", L=30.0) -> volplay.Volume:
    """A Volume per thread and (mode, L), the last few kept: building one traces every mirror (~1 s)."""
    cache = getattr(_local, "volumes", None)
    if cache is None:
        cache = _local.volumes = collections.OrderedDict()
    key = (mode, round(L, 2))
    if key in cache:
        cache.move_to_end(key)
    else:
        cache[key] = volplay.Volume(str(CASE_JSON), mode=mode, L=L)
        while len(cache) > VOLUMES_PER_THREAD:
            cache.popitem(last=False)
    return cache[key]


def scene_function(s: Settings):
    vol = volume(s.mode, s.L)
    k = s.size if s.scene in _size_scenes() else 1.0
    return vol, volplay.scene_fn(vol, s.scene, size=7.0 * k, height=14.0 * k)


def _size_scenes():
    from .catalog import SIZE_SCENES
    return SIZE_SCENES


# ---------------------------------------------------------------- playable clips
class Clip:
    """A loop of blue-only DMD frames stored as small crops (most of a frame is black). Indexing returns the
    full 1140 x 912 BGR frame, so vol2.volplay.play() can push it like a list of frames."""

    def __init__(self, parts, fps, loop_s):
        self.parts, self.fps, self.loop_s = parts, float(fps), float(loop_s)

    def __len__(self):
        return len(self.parts)

    def __getitem__(self, i):
        f = np.zeros((H, W, 3), np.uint8)
        p = self.parts[i]
        if p is not None:
            r0, c0, a = p
            f[r0:r0 + a.shape[0], c0:c0 + a.shape[1], 0] = a
        return f

    @property
    def nbytes(self):
        return sum(p[2].nbytes for p in self.parts if p is not None)


def _crop(blue):
    rows = np.flatnonzero(blue.any(axis=1))
    if not len(rows):
        return None
    cols = np.flatnonzero(blue.any(axis=0))
    r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    return int(r0), int(c0), blue[r0:r1, c0:c1].copy()


def clip_timing(s: Settings, seconds: float):
    """(frames, fps) covering one loop of the scene at this speed, or just `seconds` when that is shorter: at
    60 fps, or fewer when that would exceed MAX_FRAMES (then fps = frames / span, never above 60)."""
    span = min(seconds, volplay.PERIODS[s.scene] / s.speed)
    exact = FPS * span
    if abs(exact - round(exact)) < 1e-6 and round(exact) <= MAX_FRAMES:
        return max(1, int(round(exact))), FPS
    n = max(1, min(MAX_FRAMES, int(math.floor(exact))))
    return n, n / span


def render_clip(s: Settings, seconds: float, cancel=None, progress=None) -> Clip:
    vol, fn = scene_function(s)
    lut = duty_lut()
    n, fps = clip_timing(s, seconds)
    parts = []
    for i in range(n):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        f, _ = vol.frame(fn(s.speed * i / fps), lut, gain=s.brightness)
        parts.append(_crop(f[..., 0]))
        if progress is not None:
            progress(i + 1, n)
    return Clip(parts, fps, n / fps)


# ---------------------------------------------------------------- preview of the mirror pattern
PREVIEW_FRAMES = 24
PREVIEW_ROWS = (830, 1110)             # every scene's lit area as of 2026-10 (rows 848-1097, cols 559-786)
PREVIEW_COLS = (540, 800)
SPRITE_COLS = 6


def _png_b64(img) -> str:
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _jpg_b64(img, quality=88) -> str:
    """Soft, photo-like images (the simulated glow): JPEG is far smaller and faster to encode than PNG."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _sprite(tiles, cols=SPRITE_COLS):
    h, w = tiles[0].shape[:2]
    rows = int(math.ceil(len(tiles) / cols))
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = t
    return sheet, {"cols": cols, "rows": rows, "w": w, "h": h, "count": len(tiles)}


def _guides():
    """Face A / corner / face B column spans (Joey's 2026-10-05 call-outs) for labelling the preview."""
    import json
    m = json.loads(CASE_MAP.read_text(encoding="utf-8-sig"))
    return [{"label": "face A", "cols": m["planes"]["A"]["dmd_cols"]},
            {"label": "corner", "cols": m["corner_dmd_cols"]},
            {"label": "face B", "cols": m["planes"]["B"]["dmd_cols"]}]


def pattern_preview(s: Settings, cancel=None, progress=None) -> dict:
    """PREVIEW_FRAMES samples over one loop of what the mirrors show, cropped to the case and drawn with true
    mirror proportions (the diamond array's rows are half the column pitch, so columns are doubled)."""
    vol, fn = scene_function(s)
    lut = duty_lut()
    period = volplay.PERIODS[s.scene]
    frames = []
    for k in range(PREVIEW_FRAMES):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        f, _ = vol.frame(fn(period * k / PREVIEW_FRAMES), lut, gain=s.brightness)
        frames.append(f[..., 0])
        if progress is not None:
            progress(k + 1, PREVIEW_FRAMES)
    r0, r1 = PREVIEW_ROWS
    c0, c1 = PREVIEW_COLS
    lit = np.flatnonzero(np.any([f.any(axis=0) for f in frames], axis=0))
    if len(lit):                                       # widen if a (re-mapped) scene lights outside the default
        c0, c1 = min(c0, int(lit[0]) - 8), max(c1, int(lit[-1]) + 9)
    lit_r = np.flatnonzero(np.any([f.any(axis=1) for f in frames], axis=0))
    if len(lit_r):
        r0, r1 = min(r0, int(lit_r[0]) - 8), max(r1, int(lit_r[-1]) + 9)
    r0, r1, c0, c1 = max(0, r0), min(H, r1), max(0, c0), min(W, c1)
    tiles = []
    for f in frames:
        v = f[r0:r1, c0:c1].astype(np.float32) / 255.0
        v = np.repeat(v, 2, axis=1)                     # true aspect: column pitch = 2 x row pitch
        tile = np.zeros(v.shape + (3,), np.uint8)
        tile[..., 0] = np.round(255 * v)
        tile[..., 1] = np.round(110 * v)               # a little green so dim levels stay visible on screens
        tiles.append(tile)
    sheet, layout = _sprite(tiles)
    guides = [{"label": g["label"], "x0": 2 * (g["cols"][0] - c0), "x1": 2 * (g["cols"][1] - c0)}
              for g in _guides()]
    return {"kind": "pattern", "sprite": _png_b64(sheet), "layout": layout, "loop_s": period,
            "crop": {"rows": [r0, r1], "cols": [c0, c1]}, "guides": guides,
            "lit": bool(any(f.any() for f in frames))}


# ---------------------------------------------------------------- simulated glow in the case
SIM_FRAMES = 8
SIM_SCALE = 2
VIEWS = (("from the camera side", 30.0, 20.0), ("from above", 0.0, 90.0))
_proj_lock = threading.Lock()
_proj = {}


def _projection(vol, shape, az, el):
    """Pixel index of every voxel for an orthographic view, with bounds fixed by the whole liquid volume so the
    framing does not jump between frames. Image up = physically up."""
    key = (str(CASE_JSON), shape, az, el)          # every Volume here shares the one case geometry
    with _proj_lock:
        if key in _proj:
            return _proj[key]
    X = simulate.voxel_centres(vol.case, np.zeros(shape, np.float32)).reshape(-1, 3)
    a, e = np.radians(az), np.radians(el)
    v = np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])
    h = np.array([np.cos(a), 0.0, -np.sin(a)])
    up = np.cross(h, v)
    up /= np.linalg.norm(up)
    if el >= 89.0:                                     # looking down: put face B's far side at the top
        up = -up
    u, t = X @ h, X @ up
    u0, t1 = u.min(), t.max()
    wpx = int((u.max() - u0) / simulate.VOX) + 1
    hpx = int((t1 - t.min()) / simulate.VOX) + 1
    idx = ((t1 - t) / simulate.VOX).astype(np.int64) * wpx + ((u - u0) / simulate.VOX).astype(np.int64)
    out = (idx, hpx, wpx, (u0, t1, h, up))
    with _proj_lock:
        _proj[key] = out
    return out


def _outline(vol, img, frame_info, scale):
    """Dim outline of the liquid volume (the case interior up to the fill level)."""
    u0, t1, h, up = frame_info
    case = vol.case
    C, uA, uB = case.axes()
    lo, hi = case.t, case.S - case.t
    ys = (case.y_top, case.y_top + case.fill_mm)
    corners = {}
    for i, qa in enumerate((lo, hi)):
        for j, qb in enumerate((lo, hi)):
            for k, y in enumerate(ys):
                X = C + qa * uA + qb * uB
                X[1] = y
                corners[(i, j, k)] = (int(round((X @ h - u0) / simulate.VOX * scale)),
                                      int(round((t1 - X @ up) / simulate.VOX * scale)))
    for a_, b_ in [((0, 0, 0), (1, 0, 0)), ((0, 0, 0), (0, 1, 0)), ((1, 1, 0), (1, 0, 0)), ((1, 1, 0), (0, 1, 0)),
                   ((0, 0, 1), (1, 0, 1)), ((0, 0, 1), (0, 1, 1)), ((1, 1, 1), (1, 0, 1)), ((1, 1, 1), (0, 1, 1)),
                   ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1))]:
        cv2.line(img, corners[a_], corners[b_], (70, 70, 70), 1, cv2.LINE_AA)


def voxelise_fast(case, rays, beam_mm=1.0, step=0.25):
    """vol2.simulate.voxelise (all legs) + blur, several times faster: bincount instead of np.add.at, sample
    positions stepped in float32, OpenCV's separable Gaussian instead of np.convolve. Same model and the same total
    light; a sample lying on a voxel boundary can land in the neighbouring voxel, so single voxels differ by up to
    ~1 % of the peak (test_studio). Fine for a preview; analysis code keeps using vol2.simulate."""
    C, uA, uB = case.axes()
    lo, hi = case.t, case.S - case.t
    na = int(np.ceil((hi - lo) / simulate.VOX))
    ny = int(np.ceil(case.fill_mm / simulate.VOX))
    acc = np.zeros(ny * na * na, np.float64)
    f32 = np.float32
    for R in rays:
        for s in range(0, len(R.L), 2000):
            p0, d, L = R.p0[s:s + 2000], R.d[s:s + 2000], R.L[s:s + 2000]
            n = int(np.ceil(L.max() / step)) + 1
            tau = np.linspace(0, 1, n, dtype=f32)[None, :] * L.astype(f32)[:, None]
            # sample coordinates are linear in tau: project each ray's start and direction once (in float64),
            # then step along it in float32 voxel units (positions are within ~100 voxels: ample precision)
            a0, a1 = (((p0 - C) @ uA - lo) / simulate.VOX).astype(f32), ((d @ uA) / simulate.VOX).astype(f32)
            b0, b1 = (((p0 - C) @ uB - lo) / simulate.VOX).astype(f32), ((d @ uB) / simulate.VOX).astype(f32)
            y0, y1 = ((p0[:, 1] - case.y_top) / simulate.VOX).astype(f32), (d[:, 1] / simulate.VOX).astype(f32)
            ia = (a0[:, None] + tau * a1[:, None]).astype(np.int32).ravel()
            ib = (b0[:, None] + tau * b1[:, None]).astype(np.int32).ravel()
            iy = (y0[:, None] + tau * y1[:, None]).astype(np.int32).ravel()
            w = np.repeat(L / (n - 1), n)
            ok = (ia >= 0) & (ia < na) & (ib >= 0) & (ib < na) & (iy >= 0) & (iy < ny)
            acc += np.bincount(((iy * na + ib) * na + ia)[ok], weights=w[ok], minlength=acc.size)
    V = acc.reshape(ny, na, na).astype(np.float32)
    sig = beam_mm / 2.355 / simulate.VOX
    if sig < 0.3:
        return V
    k = cv2.getGaussianKernel(2 * int(np.ceil(3 * sig)) + 1, sig).astype(np.float32)
    one = np.ones((1, 1), np.float32)
    V = cv2.sepFilter2D(V.reshape(ny, na * na), -1, one, k, borderType=cv2.BORDER_CONSTANT).reshape(ny, na, na)
    return np.stack([cv2.sepFilter2D(V[i], -1, k, k, borderType=cv2.BORDER_CONSTANT) for i in range(ny)])


def simulated_preview(s: Settings, cancel=None, progress=None) -> dict:
    """SIM_FRAMES samples over one loop: every lit mirror traced into the liquid (all legs, incl. total internal
    reflection), as line density with a 1 mm beam, seen orthographically from two directions.
    [HEURISTIC] shape only: brightness grading, absorption and light through the corner are not modelled, so
    brightness and L do not change it (the studio's preview cache ignores them for this view)."""
    vol, fn = scene_function(s)
    lut = duty_lut()
    period = volplay.PERIODS[s.scene]
    raw = {name: [] for name, _, _ in VIEWS}
    geo = {}
    for k in range(SIM_FRAMES):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        f, _ = vol.frame(fn(period * k / SIM_FRAMES), lut, gain=s.brightness)
        V = voxelise_fast(vol.case, simulate.lit_rays(vol.case, f[..., 0] > 0), beam_mm=1.0)
        for name, az, el in VIEWS:
            idx, hpx, wpx, info = _projection(vol, V.shape, az, el)
            img = np.bincount(idx, weights=V.ravel(), minlength=hpx * wpx).reshape(hpx, wpx)
            raw[name].append(img)
            geo[name] = (hpx, wpx, info)
        if progress is not None:
            progress(k + 1, SIM_FRAMES)
    tiles = [[] for _ in range(SIM_FRAMES)]
    for name, _, _ in VIEWS:
        hpx, wpx, info = geo[name]
        top = max(float(np.percentile(np.concatenate([i.ravel() for i in raw[name]]), 99.7)), 1e-9)
        for k, img in enumerate(raw[name]):
            v = np.clip(img / top, 0, 1) ** 0.6
            v = cv2.GaussianBlur(v.astype(np.float32), (0, 0), 0.9)       # hide the voxel / mirror-row moire
            v = cv2.resize(v, (wpx * SIM_SCALE, hpx * SIM_SCALE), interpolation=cv2.INTER_LINEAR)
            tile = np.zeros(v.shape + (3,), np.uint8)
            _outline(vol, tile, info, SIM_SCALE)
            glow = np.stack([90 * v, 255 * v, 170 * v], axis=-1)          # fluorescein green-yellow (BGR)
            tiles[k].append(np.maximum(tile, np.round(glow).astype(np.uint8)))
    hmax = max(t.shape[0] for t in tiles[0])
    joined = []
    for row in tiles:
        padded = [np.pad(t, ((0, hmax - t.shape[0]), (0, 8), (0, 0))) for t in row]
        joined.append(np.concatenate(padded, axis=1))
    sheet, layout = _sprite(joined, cols=4)
    widths = [t.shape[1] + 8 for t in tiles[0]]
    return {"kind": "simulated", "sprite": _jpg_b64(sheet), "layout": layout, "loop_s": period,
            "views": [{"label": name, "x0": int(sum(widths[:i])), "w": int(widths[i] - 8)}
                      for i, (name, _, _) in enumerate(VIEWS)],
            "note": "A simulation of where light goes, not of how bright: brightness, fading in the dye and "
                    "light through the rounded corner are not shown."}
