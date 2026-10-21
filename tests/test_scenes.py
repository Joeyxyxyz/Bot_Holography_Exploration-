"""Offline checks of the volume player: every scene renders valid, blue-only DMD frames from the bundled
calibration, with no hardware."""
import numpy as np
import pytest

from vol2 import volplay as vp
from vol2.warp_scan import clean_map

SCENES = sorted(vp.SCENES)


@pytest.fixture(scope="module")
def lut():
    return vp.load_duty_lut(vp.BUNDLED / "duty_roi.json")


@pytest.fixture(scope="module")
def vol():
    return vp.Volume(str(vp.ROOT / "configs" / "case_fit_tank_v4.json"))


def test_scene_list_is_complete():
    assert len(SCENES) >= 35 and {"ribbon", "ocean", "fwc_static", "sphere_round"} <= set(SCENES)


def test_bundled_duty_curve_is_monotone_with_a_dead_zone(lut):
    v, g, path = lut
    assert path.endswith("duty_roi.json")
    assert np.all(np.diff(g) >= 0) and g[-1] == pytest.approx(1.0)
    assert g[v <= 48].max() < 0.02                       # dead zone
    assert vp.duty_to_level(0.0, lut) == 0 and vp.duty_to_level(1.0, lut) == 255
    lv = vp.duty_to_level(np.linspace(0, 1, 50), lut)
    assert np.all(np.diff(lv.astype(int)) >= 0)


def test_bundled_warp_map_covers_the_corrected_window():
    X, Y, cols, rows, keep = clean_map(vp.BUNDLED / "warp_scan")
    kept = [c for c, k in zip(cols, keep) if k]
    assert min(kept) <= 610 and max(kept) >= 750


@pytest.mark.parametrize("scene", SCENES)
def test_scene_renders_blue_only_dmd_frames(scene, vol, lut):
    fn = vp.scene_fn(vol, scene)
    frames = [vol.frame(fn(t), lut)[0] for t in np.linspace(0, vp.PERIODS[scene], 4, endpoint=False)]
    for f in frames:
        assert f.shape == (1140, 912, 3) and f.dtype == np.uint8
        assert not f[..., 1].any() and not f[..., 2].any(), "player frames are blue only (fluorescein)"
    assert any(f[..., 0].any() for f in frames), "scene lights nothing over its period"


def test_render_is_deterministic(vol, lut):
    a, _ = vp.render_clip(vol, "ribbon", fps=10, seconds=0.1, lut=lut)
    b, _ = vp.render_clip(vol, "ribbon", fps=10, seconds=0.1, lut=lut)
    assert np.array_equal(a[0], b[0])


def test_incomplete_warp_run_falls_back_to_bundled(vol, lut, tmp_path, monkeypatch):
    """A refused or unfinished capture leaves runs/<ts>_warp_scan without warp_map.npz: use the bundled map."""
    from rig import config
    (tmp_path / "20990101T000000_warp_scan").mkdir()
    monkeypatch.setattr(config, "RUNS", tmp_path)
    f = vol.frame(vp.scene_fn(vol, "fwc_static")(0.0), lut)[0]
    assert f[..., 0].any()


def test_frame_clips_mirrors_off_the_dmd(vol, lut):
    """A block wholly off the DMD lights nothing; a negative slice end must not wrap to the far edge."""
    for c, r in ((400, -4), (400, -10), (-3, 600), (-50, -50), (912 + 1, 600), (400, 1140 + 2)):
        assert not vol.frame([([(c, r)], 1.0, 0.0)], lut)[0].any(), (c, r)
    assert np.count_nonzero(vol.frame([([(400, -2)], 1.0, 0.0)], lut)[0][..., 0]) == 3   # one row on the DMD


def test_a_frame_whose_duties_are_all_zero_is_black(vol, lut):
    """A fade to zero must not renormalise 0 / 0 = NaN: casting a NaN level to uint8 is undefined, so the frame
    would be black only by luck of the platform."""
    with np.errstate(all="raise"):                                        # no 0 / 0 and no NaN cast
        f, norm = vol.frame([([(400, 600)], 0.0, 0.0), ([(500, 700)], 0.0, 3.0)], lut)
    assert not f.any() and norm == 1.0
    assert vol.frame([], lut)[1] == 1.0
    f = vol.frame([([(400, 600)], 0.0, 0.0), ([(500, 700)], 0.5, 0.0)], lut)[0][..., 0]
    assert f[600, 400] == 0 and f[700, 500] == 255                        # a lit element still renormalises to 1
