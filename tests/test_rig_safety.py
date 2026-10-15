"""Behaviour of the hardware layer with fakes: the rig lock, the safety guards, and clean-up on every exit."""
import sys
import types

import numpy as np
import pytest

from rig import bench, config
from rig.lock import RigBusy, RigLock
from rig.safety import SafetyError, check_frame

H, W = config.DMD_H, config.DMD_W


class FakeWindow:
    """Stands in for HDMIWindow: records what would have been shown."""
    instances = []

    def __init__(self, *a, **k):
        self.shown, self.events = [], []
        FakeWindow.instances.append(self)

    def show(self, frame):
        self.shown.append(check_frame(frame).copy())
        self.events.append("show")

    def hold(self, seconds):
        self.events.append("hold")

    def dark(self):
        self.show(np.zeros((H, W), np.uint8))
        self.events.append("dark")

    def close(self):
        self.events.append("close")


class BrokenWindow:
    def __init__(self, *a, **k):
        raise RuntimeError("no display")


def lock_is_free():
    try:
        RigLock().acquire().release()
        return True
    except RigBusy:
        return False


@pytest.fixture
def fake_rig(monkeypatch):
    """Hardware allowed, but the window is a fake and the camera is absent."""
    monkeypatch.delenv("DLP_NO_HARDWARE")
    FakeWindow.instances.clear()
    monkeypatch.setattr(bench, "HDMIWindow", FakeWindow)
    return FakeWindow


# ---------------------------------------------------------------- lock
def test_lock_excludes_a_second_holder_and_names_the_first():
    a = RigLock(holder="first").acquire()
    with pytest.raises(RigBusy, match="first"):
        RigLock(holder="second").acquire()
    a.release()
    assert lock_is_free()


def test_lock_context_manager_releases():
    with RigLock() as lk:
        assert lk.held and not lock_is_free()
    assert lock_is_free()


def test_lock_path_honours_config(tmp_path):
    assert RigLock().path == config.LOCK_PATH == tmp_path / "rig.lock"


# ---------------------------------------------------------------- guards
def test_frames_must_be_exact_dmd_size_uint8():
    check_frame(np.zeros((H, W), np.uint8))
    check_frame(np.zeros((H, W, 3), np.uint8))
    for bad in (np.zeros((H, W), np.float32), np.zeros((1080, 1920), np.uint8), np.zeros((W, H), np.uint8),
                np.zeros((H, W, 4), np.uint8), np.zeros((H, W, 3), np.uint16)):
        with pytest.raises(SafetyError):
            check_frame(bad)


def test_no_hardware_flag_blocks_bench_before_the_lock():
    with pytest.raises(SafetyError, match="DLP_NO_HARDWARE"):
        bench.Bench(camera=False)
    assert lock_is_free()


def test_no_hardware_flag_blocks_window_and_camera():
    from rig.camera import Camera
    from rig.hdmi import HDMIWindow
    with pytest.raises(SafetyError):
        HDMIWindow()
    with pytest.raises(SafetyError):
        Camera(1000)


def test_usb_hid_module_in_process_blocks_bench(fake_rig, monkeypatch):
    monkeypatch.setitem(sys.modules, "hid", types.ModuleType("hid"))
    with pytest.raises(SafetyError, match="USB/HID"):
        bench.Bench(camera=False)
    assert lock_is_free() and not fake_rig.instances


def test_usb_hid_loaded_mid_session_blocks_projection(fake_rig, monkeypatch):
    with bench.Bench(camera=False, min_hold_s=0) as b:
        monkeypatch.setitem(sys.modules, "usb", types.ModuleType("usb"))
        with pytest.raises(SafetyError):
            b.shoot(np.full((H, W), 255, np.uint8))
    assert lock_is_free()


def test_wrong_size_frame_never_reaches_the_window(fake_rig):
    with bench.Bench(camera=False, min_hold_s=0) as b:
        with pytest.raises(SafetyError):
            b.shoot(np.zeros((1080, 1920), np.uint8))
        assert b.window.shown == []


# ---------------------------------------------------------------- clean-up on every exit path
def test_bench_holds_lock_then_goes_dark_and_releases(fake_rig):
    with bench.Bench(camera=False, min_hold_s=0) as b:
        assert not lock_is_free()
        assert b.shoot(np.full((H, W), 255, np.uint8)) is None      # no camera: projection only
    w = fake_rig.instances[0]
    assert w.events[-2:] == ["dark", "close"] and not w.shown[-1].any()
    assert lock_is_free()


def test_bench_goes_dark_and_releases_on_error(fake_rig):
    with pytest.raises(KeyboardInterrupt):
        with bench.Bench(camera=False, min_hold_s=0) as b:
            b.shoot(np.full((H, W), 255, np.uint8))
            raise KeyboardInterrupt
    w = fake_rig.instances[0]
    assert w.events[-2:] == ["dark", "close"] and not w.shown[-1].any()
    assert lock_is_free()


def test_bench_releases_lock_when_window_fails(fake_rig, monkeypatch):
    monkeypatch.setattr(bench, "HDMIWindow", BrokenWindow)
    with pytest.raises(RuntimeError, match="no display"):
        bench.Bench(camera=False)
    assert lock_is_free()


def test_bench_darkens_and_releases_when_camera_fails(fake_rig, monkeypatch):
    import rig.camera

    class BrokenCamera:
        def __init__(self, *a, **k):
            raise RuntimeError("No FLIR camera found")

    monkeypatch.setattr(rig.camera, "Camera", BrokenCamera)
    with pytest.raises(RuntimeError, match="FLIR"):
        bench.Bench(camera=True)
    assert fake_rig.instances[0].events[-2:] == ["dark", "close"]
    assert lock_is_free()


def test_second_bench_is_refused_while_first_runs(fake_rig):
    with bench.Bench(camera=False, min_hold_s=0):
        with pytest.raises(RigBusy):
            bench.Bench(camera=False, min_hold_s=0)
    assert lock_is_free()


class FakeCamera:
    def __init__(self, *a, **k):
        self.closed = False

    def grab(self):
        return np.zeros((4, 4), np.uint8)

    def flush(self):
        self.grab()

    def set_exposure_us(self, us):
        pass

    def close(self):
        self.closed = True


def test_legacy_open_rig_pattern_releases(fake_rig, monkeypatch):
    import rig.camera
    monkeypatch.setattr(rig.camera, "Camera", FakeCamera)
    lock, sync = bench.open_rig()                        # the (lock, sync) pattern the vol2 / tools scripts use
    try:
        img = sync.shoot(np.full((H, W), 255, np.uint8))
        assert img.shape == (4, 4)
        assert not lock_is_free()
    finally:
        sync.close()
        lock.release()
    assert fake_rig.instances[0].events[-2:] == ["dark", "close"]
    assert lock_is_free()
