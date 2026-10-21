"""Holo Studio (studio/): catalogue, rendering, the local server's security rules, and the engine driving a
FAKE rig (no window, no camera, private lock and STOP files from conftest)."""
import base64
import http.client
import json
import math
import threading
import time

import cv2
import numpy as np
import pytest

from rig import bench, config
from rig.lock import RigLock, probe
from studio import catalog, clips, engine
from studio.server import StudioServer
from vol2 import volplay

H, W = volplay.H, volplay.W


# ---------------------------------------------------------------- catalogue
def test_catalogue_lists_every_scene_exactly_once():
    listed = [s for g in catalog.GROUPS for s, _, _ in g["scenes"]]
    assert sorted(listed) == sorted(volplay.SCENES) and len(listed) == len(set(listed))
    assert set(catalog.DEMO) <= set(volplay.SCENES)
    sc = catalog.scenes()
    assert all(sc[s]["title"] and sc[s]["description"] for s in sc)


def test_camera_captures_exist_where_flagged():
    flagged = {s for s, v in catalog.scenes().items() if v["camera"]}
    assert flagged == {"fw_breathe", "fw_rain", "fw_ribbon", "fwc_ripple", "fwc_rock", "fwc_scan", "fwc_split",
                       "fwc_stack"}
    assert all(catalog.camera_gif(s).read_bytes()[:3] == b"GIF" for s in flagged)


# ---------------------------------------------------------------- settings and clips
@pytest.mark.parametrize("bad", [
    {}, {"scene": "nope"}, {"scene": "ribbon", "mode": "c"}, {"scene": "ribbon", "speed": 5},
    {"scene": "ribbon", "brightness": 0.1}, {"scene": "ribbon", "size": True}, {"scene": "ribbon", "L": math.nan},
    {"scene": "ribbon", "speed": "1"}, ["ribbon"]])
def test_settings_are_validated(bad):
    with pytest.raises(ValueError):
        clips.Settings.from_dict(bad)


def test_clip_is_exactly_the_players_render_at_default_settings():
    for scene in ("ribbon", "ball_bounce"):
        s = clips.Settings(scene)
        clip = clips.render_clip(s, 0.5)                                      # 30 frames keep the test quick
        ref, _ = volplay.render_clip(clips.volume(), scene, 60, 0.5, clips.duty_lut())
        assert len(clip) == len(ref) == 30 and clip.fps == 60.0
        assert all(np.array_equal(clip[i], ref[i]) for i in range(len(ref)))
        assert clip.nbytes < sum(f.nbytes for f in ref) / 20             # crops, not full frames


def test_clip_timing_loops_seamlessly_and_caps_memory():
    assert clips.clip_timing(clips.Settings("ribbon"), 30) == (120, 60.0)
    assert clips.clip_timing(clips.Settings("ribbon"), 0.5) == (30, 60.0)            # shorter than one loop
    n, fps = clips.clip_timing(clips.Settings("ocean", speed=0.5), 60)                # a 20 s loop
    assert n == clips.MAX_FRAMES and n / fps == pytest.approx(20.0)
    n, fps = clips.clip_timing(clips.Settings("ribbon", speed=0.3), 60)
    assert n / fps == pytest.approx(2.0 / 0.3) and fps <= 60


def test_brightness_dims_and_speed_scales_time():
    s1 = clips.Settings("fw_static")
    full = clips.render_clip(s1, 1)[0][..., 0]
    dim = clips.render_clip(clips.Settings("fw_static", brightness=0.6), 1)[0][..., 0]
    assert dim.max() < full.max() and ((dim > 0) <= (full > 0)).all()
    slow = clips.render_clip(clips.Settings("ribbon", speed=0.5), 0.1)
    assert len(slow) == 6 and np.array_equal(slow[2], clips.render_clip(clips.Settings("ribbon"), 0.1)[1])


def _decode(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def test_pattern_preview_and_simulated_view_render(monkeypatch):
    monkeypatch.setattr(clips, "SIM_FRAMES", 2)                              # the full 8 take ~5 s
    p = clips.pattern_preview(clips.Settings("ribbon"))
    L = p["layout"]
    img = _decode(p["sprite"])
    assert img.shape[:2] == (L["rows"] * L["h"], L["cols"] * L["w"]) and L["count"] == clips.PREVIEW_FRAMES
    assert p["lit"] and img[..., 0].max() > 200 and [g["label"] for g in p["guides"]] == ["face A", "corner", "face B"]
    q = clips.simulated_preview(clips.Settings("ball_bounce"))
    img = _decode(q["sprite"])
    assert q["layout"]["count"] == clips.SIM_FRAMES and img[..., 1].max() > 100 and len(q["views"]) == 2
    assert "HEURISTIC" in q["note"]


# ---------------------------------------------------------------- rig probe
def test_probe_reports_free_busy_and_writes_nothing(tmp_path):
    assert probe() == (True, "") and not config.LOCK_PATH.exists()         # never creates the lock file
    with RigLock(holder="scanner-test"):
        info = config.LOCK_PATH.with_suffix(".info.json").read_text(encoding="utf-8")
        free, holder = probe()
        assert not free and "scanner-test" in holder
        assert config.LOCK_PATH.with_suffix(".info.json").read_text(encoding="utf-8") == info
    assert probe() == (True, "")


# ---------------------------------------------------------------- server (preview-only studio)
@pytest.fixture
def server():
    srv = StudioServer(engine.Studio(), 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, method, path, body=None, headers=None, token=True):
    c = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=30)
    h = {"Host": f"127.0.0.1:{srv.port}"}
    if token:
        h["X-Holo-Token"] = srv.token
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    try:
        return r.status, json.loads(raw), r
    except ValueError:
        return r.status, raw, r


def test_page_carries_the_token_and_strict_headers(server):
    status, html, r = call(server, "GET", "/", token=False)
    assert status == 200 and server.token.encode() in html
    assert r.getheader("X-Frame-Options") == "DENY" and "frame-ancestors 'none'" in r.getheader("Content-Security-Policy")
    assert b"<script>" not in html                                         # no inline script (CSP)


def test_api_needs_the_token_and_the_right_host(server):
    assert call(server, "GET", "/api/state", token=False)[0] == 403
    assert call(server, "GET", "/api/state", headers={"X-Holo-Token": "guess"})[0] == 403
    assert call(server, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 403          # DNS rebinding
    assert call(server, "GET", "/", token=False, headers={"Host": f"evil.example:{server.port}"})[0] == 403
    status, st, _ = call(server, "GET", "/api/state")
    assert status == 200 and st["hardware"] is False and st["activity"] == "idle"


def test_writes_must_be_same_origin_json(server):
    ok = {"scene": "ribbon", "seconds": 5}
    assert call(server, "POST", "/api/play", ok, headers={"Origin": "http://evil.example"})[0] == 403
    assert call(server, "POST", "/api/play", b"scene=ribbon",
                headers={"Content-Type": "application/x-www-form-urlencoded"})[0] == 415
    assert call(server, "POST", "/api/play", ok, token=False)[0] == 403
    assert call(server, "POST", "/api/play", b"x" * 70000)[0] == 413
    assert call(server, "OPTIONS", "/api/play")[0] == 405


def test_preview_only_studio_refuses_to_play_but_previews(server):
    status, body, _ = call(server, "POST", "/api/play", {"scene": "ribbon", "seconds": 5})
    assert status == 409 and "Preview only" in body["error"]
    assert call(server, "POST", "/api/grid", {"seconds": 10})[0] == 409
    assert call(server, "POST", "/api/play", {"scene": "nope"})[0] == 400                    # validated first
    deadline = time.time() + 120
    while True:
        status, body, _ = call(server, "GET", "/api/preview?scene=plane_flat&mode=ab")
        if status == 200 or time.time() > deadline:
            break
        assert status == 202
        time.sleep(0.2)
    assert status == 200 and body["kind"] == "pattern"
    assert call(server, "GET", "/api/preview?scene=../x")[0] == 400
    assert call(server, "GET", "/figures/../README.md", token=False)[0] == 404
    assert call(server, "GET", "/figures/fw_ribbon", token=False)[0] == 200


def test_stop_always_answers(server):
    status, body, _ = call(server, "POST", "/api/stop", {})
    assert status == 200 and body == {"stopping": False} and config.STOP.exists()


# ---------------------------------------------------------------- engine on a fake rig
class FakeWindow:
    instances = []

    def __init__(self, *a, **k):
        self.shown, self.events = [], []
        FakeWindow.instances.append(self)

    def show(self, frame):
        self.shown.append(frame.shape)
        self.events.append("show")

    def hold(self, seconds):
        time.sleep(max(seconds, 0.001))

    def dark(self):
        self.events.append("dark")

    def close(self):
        self.events.append("close")


@pytest.fixture
def live(monkeypatch):
    """A live studio whose Bench opens a FakeWindow; its rig worker runs on a thread here."""
    import rig.camera
    monkeypatch.delenv("DLP_NO_HARDWARE")
    FakeWindow.instances.clear()
    monkeypatch.setattr(bench, "HDMIWindow", FakeWindow)

    class NoCamera:
        def __init__(self, *a, **k):
            raise AssertionError("the studio must not open the camera")
    monkeypatch.setattr(rig.camera, "Camera", NoCamera)
    st = engine.Studio()
    done = threading.Event()
    t = threading.Thread(target=st.run_forever, args=(done,), daemon=True)
    t.start()
    yield st
    st.stop()
    done.set()
    t.join(10)


def wait_idle(st, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        s = st.snapshot()
        if not s["busy"]:
            return s
        time.sleep(0.05)
    raise AssertionError("studio did not finish")


def lock_free():
    return probe()[0]


def test_engine_plays_a_scene_then_blanks_and_releases(live):
    assert live.snapshot()["hardware"] is True
    live.submit_play({"scene": "plane_flat", "seconds": 1})
    s = wait_idle(live)
    assert s["last"]["status"] == "done" and s["last"]["results"][0]["shown"] > 5
    w = FakeWindow.instances[-1]
    assert w.events[-2:] == ["dark", "close"] and lock_free()


def test_engine_refuses_a_second_job_while_busy(live):
    live.submit_play({"scene": "plane_flat", "seconds": 3})
    with pytest.raises(engine.Refused) as e:
        live.submit_play({"scene": "ribbon", "seconds": 3})
    assert e.value.status == 409
    live.stop()
    wait_idle(live)


def test_stop_ends_playback_quickly_and_releases(live):
    live.submit_play({"scene": "plane_flat", "seconds": 60})
    end = time.time() + 60
    while live.snapshot()["activity"] != "playing" and time.time() < end:
        time.sleep(0.05)
    t0 = time.time()
    live.stop()
    s = wait_idle(live)
    assert time.time() - t0 < 2.0 and s["last"]["status"] == "stopped"
    assert FakeWindow.instances[-1].events[-2:] == ["dark", "close"] and lock_free()
    assert not config.STOP.exists()                       # consumed by the player that held the rig


def test_busy_rig_is_reported_and_never_broken(live):
    with RigLock(holder="swiss_army_scanner"):
        live.submit_play({"scene": "plane_flat", "seconds": 1})
        s = wait_idle(live)
        assert s["last"]["status"] == "busy" and "swiss_army_scanner" in s["last"]["message"]
        assert not lock_free()                            # still the other program's
    assert not FakeWindow.instances


def test_playlist_runs_in_order_and_stop_cancels_the_rest(live):
    live.submit_playlist({"items": [{"scene": "plane_flat", "seconds": 1}, {"scene": "fw_static", "seconds": 1}]})
    s = wait_idle(live)
    assert s["last"]["status"] == "done" and [r["title"] for r in s["last"]["results"]] == ["Thin plane", "Thick plane"]
    live.submit_playlist({"items": [{"scene": "plane_flat", "seconds": 30}, {"scene": "fw_static", "seconds": 30}]})
    end = time.time() + 60
    while live.snapshot()["activity"] != "playing" and time.time() < end:
        time.sleep(0.05)
    live.stop()
    s = wait_idle(live)
    assert s["last"]["status"] == "stopped" and len(s["last"]["results"]) <= 1


def test_playlist_and_grid_limits(live):
    with pytest.raises(engine.Refused):
        live.submit_playlist({"items": [{"scene": "ribbon", "seconds": 600}] * 4})               # 40 min
    with pytest.raises(engine.Refused):
        live.submit_playlist({"items": [{"scene": "ribbon", "seconds": 5}] * 21})
    with pytest.raises(engine.Refused):
        live.submit_grid({"seconds": 4000})
    with pytest.raises(engine.Refused):
        live.submit_play({"scene": "ribbon", "seconds": 0})


def test_grid_is_held_white_and_full_size(live):
    live.submit_grid({"seconds": 5})
    end = time.time() + 30
    while live.snapshot()["activity"] != "holding" and time.time() < end:
        time.sleep(0.05)
    time.sleep(0.3)
    live.stop()
    s = wait_idle(live)
    assert s["last"]["status"] == "stopped"
    assert FakeWindow.instances[-1].shown[0] == (H, W) and engine.grid_frame().max() == 255


def test_fast_voxelise_matches_the_model():
    from vol2 import simulate
    vol, fn = clips.scene_function(clips.Settings("ball_bounce"))
    f, _ = vol.frame(fn(0.3), clips.duty_lut())
    rays = simulate.lit_rays(vol.case, f[..., 0] > 0)
    V = simulate.voxelise(vol.case, rays, beam_mm=1.0)
    F = clips.voxelise_fast(vol.case, rays, beam_mm=1.0)
    assert F.shape == V.shape and np.abs(F - V).max() <= 1e-5 * V.max()


def test_previewer_drops_a_stale_render_for_new_settings(monkeypatch):
    started = threading.Event()

    def slow(s, cancel=None, progress=None):
        started.set()
        for _ in range(500):
            if cancel.is_set():
                raise clips.Cancelled()
            time.sleep(0.01)
        return {"kind": "simulated"}
    monkeypatch.setattr(clips, "simulated_preview", slow)
    monkeypatch.setattr(clips, "pattern_preview", lambda s, cancel=None, progress=None: {"kind": "pattern"})
    pv = engine.Previewer()
    pv.request("simulated", clips.Settings("ribbon"))
    assert started.wait(5)
    t0 = time.time()
    while pv.request("pattern", clips.Settings("ocean"))["state"] != "done":
        assert time.time() - t0 < 3, "the new request waited for the stale render"
        time.sleep(0.02)
    assert pv.key("simulated", clips.Settings("ribbon")) not in pv._jobs
