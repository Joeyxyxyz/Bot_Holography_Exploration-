"""Offline checks of the 1440 Hz sub-frame packer (vol2/subframe.py): the slot spread, the duty thresholds, the
1-bit rasteriser, and what build() and plane_check() write. Files go to a pytest tmp_path; nothing is projected.
The 24-plane pack / unpack round trip itself is in test_vol2.py."""
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from vol2 import flashpack
from vol2 import subframe as sf
from vol2 import volplay as vp

H, W = 1140, 912
# the slot a growing duty lights next: 5-bit bit reversal of 0..23, ranked (halves, quarters, eighths, ...)
ORDER = [0, 12, 6, 18, 3, 15, 9, 21, 2, 14, 8, 20, 5, 17, 11, 23, 1, 13, 7, 19, 4, 16, 10, 22]


def lit_slots(d):
    return np.nonzero(d > sf._THR)[0]


@pytest.fixture(scope="module")
def vol():
    return vp.Volume(str(vp.ROOT / "configs" / "case_fit_tank_v4.json"))


@pytest.fixture(scope="module")
def lut():
    return vp.load_duty_lut(vp.BUNDLED / "duty_roi.json")


@pytest.fixture
def out(tmp_path, monkeypatch):
    """build / plane_check / preview write here, never into the repo's vol2/out."""
    monkeypatch.setattr(sf, "OUT", tmp_path / "subframe")
    return tmp_path / "subframe"


# ---------------------------------------------------------------- slot spread and duty thresholds
def test_every_slot_has_its_own_threshold():
    assert sf.SUB == 24 and sf.SUB_HZ == 1440
    assert sorted(np.argsort(sf._ORDER).tolist()) == list(range(24))      # each slot ranked exactly once
    assert np.allclose(np.sort(sf._THR), (np.arange(24) + 0.5) / 24)


def test_slot_spread_is_the_bit_reversed_interleave():
    assert np.argsort(sf._THR).tolist() == ORDER
    for n in (2, 4, 8):                                                   # first 2^m lit slots evenly spaced
        assert set(np.diff(sorted(ORDER[:n]))) == {24 // n}, n
    for n in range(25):                                                   # any duty: halves, quarters and
        lit = np.zeros(24, int)                                           # eighths of the frame differ by at
        lit[ORDER[:n]] = 1                                                # most one lit slot
        for blocks in (2, 4, 8):
            c = lit.reshape(blocks, -1).sum(1)
            assert c.max() - c.min() <= 1, (n, blocks, c)


def test_duty_lights_round_24d_slots_and_an_exact_half_rounds_down():
    """Slot k is on while d > (rank_k + 0.5) / 24: d lights round(24 d) slots, the first ones of ORDER."""
    assert len(lit_slots(0.0)) == 0 and len(lit_slots(1.0)) == 24
    for j in range(25):
        assert set(lit_slots(j / 24).tolist()) == set(ORDER[:j]), j
        if j < 24:
            assert len(lit_slots((j + 0.5) / 24)) == j                    # down (Python's round() goes to even)
    d = np.random.default_rng(0).random(2000)
    d = d[np.abs(24 * d % 1 - 0.5) > 1e-9]
    assert all(len(lit_slots(x)) == round(24 * x) for x in d)
    prev = set()
    for x in np.linspace(-0.1, 1.1, 1201):                                # monotone and nested: a higher duty
        s = set(lit_slots(x).tolist())                                    # only ever adds slots
        assert prev <= s, x
        prev = s
    assert len(prev) == 24


# ---------------------------------------------------------------- the 1-bit rasteriser
def test_raster_binary_blocks_threshold_and_edges():
    f = sf.raster_binary([([(400, 600)], 1.0, 0.0)], 0.5)
    assert f.shape == (H, W) and f.dtype == np.uint8 and set(np.unique(f).tolist()) == {0, 255}
    ys, xs = np.nonzero(f)
    assert (xs.min(), xs.max(), ys.min(), ys.max(), len(xs)) == (399, 401, 598, 602, 15)   # 3 cols x 5 rows
    assert np.count_nonzero(sf.raster_binary([([(400, 600)], 1.0, 0.0)], 0.5, wc=1, wr=1)) == 1
    assert not sf.raster_binary([([(400, 600)], 0.5, 0.0)], 0.5).any()                    # strictly above
    assert sf.raster_binary([([(400, 600)], 0.5 + 1e-9, 0.0)], 0.5).any()
    assert not sf.raster_binary([], 0.0).any()
    two = sf.raster_binary([([(400, 600), (401, 600)], 1.0, 0.0), ([(100, 200)], 0.2, 0.0)], 0.1)
    assert np.count_nonzero(two) == 4 * 5 + 15                                            # union of blocks
    assert np.count_nonzero(sf.raster_binary([([(0, 0)], 1.0, 0.0)], 0.5)) == 2 * 3        # clipped at the
    assert np.count_nonzero(sf.raster_binary([([(W - 1, H - 1)], 1.0, 0.0)], 0.5)) == 2 * 3   # DMD corners


def test_raster_binary_lights_what_the_60hz_rasteriser_lights(vol, lut):
    for scene, t in (("ribbon", 0.3), ("sphere_round", 0.0), ("fw_ribbon", 0.7)):
        els = vp.scene_fn(vol, scene)(t)
        f60 = vol.frame(els, lut)[0][..., 0]
        assert np.array_equal(sf.raster_binary(els, 0.0) > 0, f60 > 0), scene


# ---------------------------------------------------------------- sub-frames of one HDMI frame
def test_slot_k_samples_the_scene_at_i_over_60_plus_k_over_1440():
    seen = []
    subs = sf.subframes(SimpleNamespace(L=30.0), lambda t: seen.append(t) or [], 3)
    assert np.allclose(seen, 3 / 60 + np.arange(24) / 1440)
    assert len(subs) == 24 and not any(s.any() for s in subs)


def test_subframes_light_each_element_in_its_duty_share():
    v = SimpleNamespace(L=30.0)
    els = [([(100, 100)], 1.0, 0.0), ([(300, 300)], 0.5, 0.0), ([(500, 500)], 0.25, 0.0), ([(700, 700)], 0.04, 0.0)]
    subs = sf.subframes(v, lambda t: els, 0)

    def on(c, r):
        return [k for k, s in enumerate(subs) if s[r, c]]
    assert on(100, 100) == list(range(24)) and on(300, 300) == sorted(ORDER[:12])
    assert on(500, 500) == sorted(ORDER[:6]) and on(700, 700) == [0]
    # absorption compensation: duty x exp(tau / L), renormalised so the brightest element is 1
    subs = sf.subframes(v, lambda t: [([(100, 100)], 1.0, 0.0), ([(300, 300)], 1.0, 30.0 * np.log(2))], 0)
    assert on(100, 100) == sorted(ORDER[:12]) and on(300, 300) == list(range(24))


def test_a_sub_frame_whose_duties_are_all_zero_stays_dark():
    """A fade to zero must not renormalise 0 / 0 = NaN, which `d <= threshold` would let through as fully on."""
    v = SimpleNamespace(L=30.0)
    with np.errstate(all="ignore"):
        subs = sf.subframes(v, lambda t: [([(100, 100)], 0.0, 0.0), ([(300, 300)], 0.0, 5.0)], 0)
    assert not any(s.any() for s in subs)
    with np.errstate(all="raise"):                                        # and no 0 / 0 on the way
        sf.subframes(v, lambda t: [([(100, 100)], 0.0, 0.0)], 0)
    subs =sf.subframes(v, lambda t: [([(100, 100)], 0.0, 0.0), ([(300, 300)], 0.5, 0.0)], 0)
    assert not any(s[100, 100] for s in subs) and all(s[300, 300] for s in subs)
    assert not sf.raster_binary([([(100, 100)], float("nan"), 0.0)], 0.5).any()


# ---------------------------------------------------------------- files: build() and plane_check()
def test_build_writes_frames_info_and_procedure(out, vol):
    d = sf.build("ribbon", seconds=2 / 60)
    assert d == out / "ribbon_ab"
    files = sorted((d / "frames").glob("*.png"))
    assert [p.name for p in files] == ["f0000.png", "f0001.png"]
    info = json.loads((d / "info.json").read_text())
    assert info.pop("render_s") >= 0
    assert info == {"scene": "ribbon", "mode": "ab", "hdmi_frames": 2, "subframes": 48, "subframe_hz": 1440.0,
                    "subframe_us": 694.4}
    fn = vp.scene_fn(vol, "ribbon")
    for i, p in enumerate(files):
        img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        assert img.shape == (H, W, 3) and img.dtype == np.uint8
        planes = flashpack.unpack(img, 24)
        for k, pl in enumerate(planes):            # bit k = slot k = the scene at i/60 + k/1440 (ribbon: duty 1)
            assert np.array_equal(pl, sf.raster_binary(fn((i * 24 + k) / 1440), 0.0)), (i, k)
        assert not np.array_equal(planes[0], planes[23])                   # the ribbon moves within a frame
    txt = (d / "procedure.txt").read_text(encoding="utf-8")
    exp = int(1e6 / sf.SUB_HZ) - 4                                         # inside the 694 us slot
    assert "sent nothing to the projector" in txt and f"= {exp} us" in txt and 24 * exp <= 1e6 / 60
    assert "Joey" in txt and "Back to Video Mode" in txt


def test_a_shorter_rebuild_leaves_no_stale_frames(out):
    """`subframe play` loops every frames/f*.png: frames left from a longer build would play as part of the loop."""
    sf.build("wave_A", seconds=3 / 60)
    d = sf.build("wave_A", seconds=1 / 60)
    assert [p.name for p in sorted((d / "frames").glob("f*.png"))] == ["f0000.png"]
    assert json.loads((d / "info.json").read_text())["hdmi_frames"] == 1


def test_plane_check_puts_digit_k_in_slot_k(out):
    d = sf.plane_check()
    assert d == out / "plane_check"
    img = cv2.imread(str(d / "plane_check.png"), cv2.IMREAD_UNCHANGED)
    assert img.shape == (H, W, 3) and img.dtype == np.uint8
    assert np.array_equal(img, cv2.imread(str(d / "frames" / "f0000.png"), cv2.IMREAD_UNCHANGED))
    b, g, r = (img[..., i] for i in range(3))
    digits = [flashpack.digit_frame(k) > 0 for k in range(24)]
    for k in range(24):                            # read from the bytes, not via unpack: G0-G7, R0-R7, B0-B7
        byte, bit = (g, k) if k < 8 else (r, k - 8) if k < 16 else (b, k - 16)
        assert np.array_equal((byte >> bit) & 1 == 1, digits[k]), k
    assert all(not np.array_equal(digits[k], digits[j]) for k in range(24) for j in range(k))   # swaps show
