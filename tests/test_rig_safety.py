"""Behaviour of the hardware layer with fakes: the rig lock, the safety guards, and clean-up on every exit."""
import os
import sys
import types
from pathlib import Path

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


class GuardCamera:
    def __init__(self, *a, **k):
        raise AssertionError("a test reached the real camera: patch rig.camera.Camera with a fake")


@pytest.fixture
def fake_rig(monkeypatch):
    """Hardware guard off, so every real device class is replaced: the window by FakeWindow and the camera by a
    guard that fails the test. A test that wants a camera patches rig.camera.Camera itself."""
    import rig.camera
    import rig.hdmi
    monkeypatch.delenv("DLP_NO_HARDWARE")
    FakeWindow.instances.clear()
    monkeypatch.setattr(bench, "HDMIWindow", FakeWindow)
    monkeypatch.setattr(rig.hdmi, "HDMIWindow", FakeWindow)
    monkeypatch.setattr(rig.camera, "Camera", GuardCamera)
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


def test_default_lock_is_the_scanners_file():
    """Same file as the swiss-army-scanner's RigLock, so the two programs exclude each other."""
    assert config.default_lock(r"C:\ProgramData") == Path(r"C:\ProgramData") / "swiss_army_scanner" / "rig.lock"
    assert RigLock(path=config.default_lock(r"C:\ProgramData")).info_path.name == "rig.info.json"
    assert "DLP_RIG_LOCK" not in Path(config.__file__).read_text(encoding="utf-8")    # not configurable


@pytest.mark.skipif(os.name != "nt", reason="the bench lock is msvcrt on Windows")
def test_lock_is_a_byte_lock_on_byte_0():
    """The scanner locks byte 0 with msvcrt.locking(LK_NBLCK, 1): a foreign handle must find byte 0 locked."""
    import msvcrt
    with RigLock():
        with open(config.LOCK_PATH, "rb") as fh:
            fh.seek(0)
            with pytest.raises(OSError):
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)


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


def test_close_is_idempotent_and_never_repaints(fake_rig):
    b = bench.Bench(camera=False, min_hold_s=0)
    b.close()
    n = len(fake_rig.instances[0].events)
    b.close()
    assert len(fake_rig.instances[0].events) == n and lock_is_free()


def test_camera_closes_before_the_lock_even_if_dark_fails(fake_rig, monkeypatch):
    import rig.camera
    cams = []

    class Cam(FakeCamera):
        def __init__(self, *a, **k):
            super().__init__()
            cams.append(self)

    class DarkFails(FakeWindow):
        def dark(self):
            raise KeyboardInterrupt                          # e.g. a second Ctrl+C during clean-up

    monkeypatch.setattr(rig.camera, "Camera", Cam)
    monkeypatch.setattr(bench, "HDMIWindow", DarkFails)
    b = bench.Bench(camera=True, min_hold_s=0)
    with pytest.raises(KeyboardInterrupt):
        b.close()
    assert cams[0].closed and fake_rig.instances[0].events[-1] == "close" and lock_is_free()


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


# ---------------------------------------------------------------- the real HDMIWindow, with a fake OpenCV
class FakeCv2(types.ModuleType):
    WINDOW_NORMAL = WND_PROP_FULLSCREEN = WINDOW_FULLSCREEN = COLOR_GRAY2BGR = 0

    def __init__(self, rect):
        super().__init__("cv2")
        self.rect, self.calls, self.shown = rect, [], []

    def namedWindow(self, *a):
        self.calls.append("namedWindow")

    def moveWindow(self, *a):
        self.calls.append("moveWindow")

    def setWindowProperty(self, *a):
        self.calls.append("fullscreen")

    def waitKey(self, *a):
        return -1

    def imshow(self, name, f):
        self.calls.append("imshow")
        self.shown.append(f.copy())

    def getWindowImageRect(self, name):
        return self.rect

    def destroyWindow(self, name):
        self.calls.append("destroyWindow")

    def cvtColor(self, f, code):
        return np.dstack([f, f, f])


@pytest.fixture
def fake_cv2(monkeypatch):
    monkeypatch.delenv("DLP_NO_HARDWARE")

    def make(rect):
        m = FakeCv2(rect)
        monkeypatch.setitem(sys.modules, "cv2", m)
        return m
    return make


def test_window_paints_black_and_checks_its_rect_before_any_content(fake_cv2):
    from rig.hdmi import HDMIWindow
    cv = fake_cv2((1920, 0, W, H))
    w = HDMIWindow()
    assert w.rect_ok and cv.calls[:3] == ["namedWindow", "moveWindow", "fullscreen"]
    assert len(cv.shown) == 2 and not any(f.any() for f in cv.shown)        # black, before anything else
    w.show(np.full((H, W), 255, np.uint8))
    w.dark()
    assert not cv.shown[-1].any()
    w.close()
    assert cv.calls[-1] == "destroyWindow"


@pytest.mark.parametrize("rect", [(0, 0, 1920, 1080), (1920, 0, 1824, 2280), (3840, 0, W, H)])
def test_window_refuses_a_scaled_or_misplaced_display(fake_cv2, rect):
    from rig.hdmi import HDMIWindow
    cv = fake_cv2(rect)
    with pytest.raises(SafetyError, match="scaled or on the wrong monitor"):
        HDMIWindow()
    assert cv.calls[-1] == "destroyWindow"
    assert not any(f.any() for f in cv.shown)                             # nothing but black was shown


def test_window_rechecks_usb_hid_on_every_frame(fake_cv2, monkeypatch):
    from rig.hdmi import HDMIWindow
    fake_cv2((1920, 0, W, H))
    w = HDMIWindow()
    monkeypatch.setitem(sys.modules, "usb1", types.ModuleType("usb1"))
    with pytest.raises(SafetyError, match="USB/HID"):
        w.show(np.full((H, W), 255, np.uint8))
