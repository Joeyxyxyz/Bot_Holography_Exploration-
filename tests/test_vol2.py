"""Checks for the two-plane model. Run: python -m pytest tests"""
import tempfile
from pathlib import Path

import numpy as np

from vol2 import flashpack
from vol2.geometry import Case, crossing_angle_deg, in_liquid, pixel_dirs, refract, trace
from vol2.render import Plane, cube_points, joint_box, pair


def test_refract_snell():
    n = np.array([0.0, 0.0, -1.0])
    t, ok = refract(np.array([[0.0, 0.0, 1.0]]), n, 1 / 1.333)
    assert ok.all() and np.allclose(t, [[0, 0, 1]])
    i = np.radians(45)
    d = np.array([[np.sin(i), 0.0, np.cos(i)]])
    t, ok = refract(d, n, 1 / 1.333)
    assert abs(np.sin(i) / np.hypot(t[0, 0], t[0, 1]) - 1.333) < 1e-9


def test_default_pose_is_the_original_model():
    c = Case()
    C, _, _ = c.axes()
    assert np.allclose(C, [0, 0, c.D]) and np.allclose(pixel_dirs(c, c.col_corner, c.row_ref), [0, 0, 1])
    assert abs(c.y_base - (c.row_base - c.row_ref) / c.rpm) < 1e-9


def test_crossing_angle_collimated_and_fan():
    """Collimated corner-on limit = 2 * (45 - asin(sin45 / n)); traced direct legs follow the fan formula
    90 - asin(sin(45 + a) / n) - asin(sin(45 + b) / n), a / b = air azimuths from the corner ray."""
    for n_liq, want in ((1.333, 25.9), (1.47, 32.5)):
        coll = 2 * (45 - np.degrees(np.arcsin(np.sin(np.radians(45)) / n_liq)))
        assert abs(coll - want) < 0.1, coll
        c = Case(n_liq=n_liq)
        for ca, cb in ((620, 662), (600, 690), (570, 720)):
            a = trace(c, "A", [ca], [820])
            b = trace(c, "B", [cb], [820])
            got = crossing_angle_deg(a, b)
            az = lambda col: abs(np.degrees(np.arctan2(pixel_dirs(c, col, 820)[0], pixel_dirs(c, col, 820)[2])))
            fan = 90 - np.degrees(np.arcsin(np.sin(np.radians(45 + az(ca))) / n_liq)) \
                     - np.degrees(np.arcsin(np.sin(np.radians(45 + az(cb))) / n_liq))
            assert abs(got - fan) < 0.3, (n_liq, ca, cb, got, fan)
            assert got < want, (got, want)                      # the fan lowers the angle


def test_direct_legs_enter_on_inner_wall_and_stay_inside():
    c = Case()
    C, uA, uB = c.axes()
    for f, inward in (("A", uB), ("B", uA)):
        R = trace(c, f, np.arange(*(c.planeA_cols if f == "A" else c.planeB_cols), 5), np.arange(700, 1000, 25))
        D = R.direct()
        assert len(D.L) > 0
        assert np.allclose((D.p0 - C) @ inward, c.t, atol=1e-6)
        assert in_liquid(c, R.p0 + 0.5 * R.L[:, None] * R.d).all()      # every leg, reflected ones too


def test_total_internal_reflection_and_absorbing_walls():
    """Review: ~2/3 of each family is totally reflected (water); taped back walls absorb instead."""
    c = Case()
    R = trace(c, "A", np.arange(*c.planeA_cols, 2), np.arange(700, 1000, 10))
    d = R.leg == 0
    frac = float(np.mean(R.end[d] == "tir"))
    assert 0.6 < frac < 0.75, frac
    # walk-off: a first reflected leg starts ~2 t tan(theta_acr) ~ 3.2-3.4 mm from its hit, along the wall
    hit = R.p0[d] + R.L[d][:, None] * R.d[d]
    m = R.mirror[d][R.end[d] == "tir"]
    leg1 = {int(k): i for i, k in enumerate(R.mirror) if R.leg[i] == 1}
    walks = [np.linalg.norm(R.p0[leg1[int(k)]] - hit[np.nonzero(R.mirror[d] == k)[0][0]])
             for k in m[:200] if int(k) in leg1]
    assert walks and 2.5 < np.median(walks) < 3.6, np.median(walks)
    ca = Case(back_walls="absorb")
    Ra = trace(ca, "A", np.arange(*ca.planeA_cols, 2), np.arange(700, 1000, 10))
    assert np.mean(Ra.end[Ra.leg == 0] == "absorbed") > 0.85


def test_joint_box_and_paired_crossings():
    """Every sample of the joint box is reachable by both families; paired A/B crossings land on the targets."""
    c = Case()
    planes = {f: Plane(c, f) for f in ("A", "B")}
    centre, side, both, q = joint_box(c, planes)
    print("joint box side", round(side, 2), "mm")
    assert side >= 12.0, side
    X = cube_points(c, side, 0.0, centre=centre)[0]
    P = pair(planes, X)
    assert P["ok"].mean() > 0.98, P["ok"].mean()
    assert np.median(P["err"][P["ok"]]) < 0.6, np.median(P["err"][P["ok"]])


def test_model_faces_vs_callouts():
    """Call-outs are 28-col cell boundaries: face A starts in cell 5 (the 12:37 scan shows the silhouette at
    ~534-541), and 740 is the grid EDGE, so it is only a lower bound for face B's end."""
    c = Case(r_corner=0.0)
    a = trace(c, "A", np.arange(500, 642), np.array([820])).direct()
    b = trace(c, "B", np.arange(643, 800), np.array([820])).direct()
    assert 530 <= a.cols.min() <= 550, a.cols.min()
    assert b.cols.max() >= 734, b.cols.max()


def test_flashpack_round_trip_and_16_slot_limit():
    rng = np.random.default_rng(1)
    frames = [(rng.random((1140, 912)) > 0.5).astype(np.uint8) * 255 for _ in range(24)]
    back = flashpack.unpack(flashpack.pack(frames), 24)
    assert all(np.array_equal(a, b) for a, b in zip(frames, back))
    with tempfile.TemporaryDirectory() as d:
        man = flashpack.write_pack(Path(d) / "p", frames[:16], [f"f{k}" for k in range(16)], exposure_us=20000)
        assert man["round_trip_from_disk_ok"] and man["gr_swap_is_pure_rotation"]
        assert (Path(d) / "p" / "procedure.txt").exists()
        try:
            flashpack.write_pack(Path(d) / "q", frames[:17], [f"f{k}" for k in range(17)])
            raise AssertionError("17 frames should be refused")
        except ValueError:
            pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
