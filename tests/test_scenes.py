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


def _frame_reference(vol, elements, lut, wc=3, wr=5):
    """The original block-by-block rasteriser (before vectorising Volume.frame), kept as the reference."""
    dmap = np.zeros((vp.H, vp.W), np.float32)
    comp = [d * np.exp(t / vol.L) for _, d, t in elements]
    norm = max(comp) if comp else 1.0
    for (mirrors, _, _), dc in zip(elements, comp):
        dd = dc / norm
        for c, r in mirrors:
            sl = (slice(max(0, r - wr // 2), min(vp.H, r + wr // 2 + 1)),
                  slice(max(0, c - wc // 2), min(vp.W, c + wc // 2 + 1)))
            dmap[sl] = np.maximum(dmap[sl], dd)
    f = np.zeros((vp.H, vp.W, 3), np.uint8)
    f[..., 0] = vp.duty_to_level(dmap, lut)
    return f, norm


@pytest.mark.parametrize("scene", SCENES)
def test_vectorised_frame_is_byte_identical_to_the_original(scene, vol, lut):
    fn = vp.scene_fn(vol, scene)
    for t in (0.0, 0.37 * vp.PERIODS[scene]):
        els = fn(t)
        f1, n1 = vol.frame(els, lut)
        f0, n0 = _frame_reference(vol, els, lut)
        assert n1 == n0 and np.array_equal(f1, f0)


def test_frame_gain_scales_duty(vol, lut):
    els = vp.scene_fn(vol, "fw_static")(0.0)
    full, half = vol.frame(els, lut)[0][..., 0], vol.frame(els, lut, gain=0.5)[0][..., 0]
    assert full.max() == 255 and 0 < half.max() < 255 and ((half > 0) <= (full > 0)).all()
