"""Coherent-build design study (holo/coherent_build.py): arithmetic model, no hardware."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "holo"))
import coherent_build as cb  # noqa: E402


def test_constants_match_fresnel_cube():
    fc = pytest.importorskip("fresnel_cube")
    assert (cb.LAM, cb.CELL, cb.ROWS, cb.CCOLS, cb.F_C, cb.ZS) == (fc.LAM, fc.CELL, fc.ROWS, fc.CCOLS, fc.F_C, fc.ZS)


def test_power_matches_prep_t3():
    prep = pytest.importorskip("prep")
    rows = {r["case"]: r for r in prep.t3_budget(cb.EFF_WINDOW)["rows"]}
    for case, d, fw in (("led_pin75_nofilter", 0.075, 30), ("led_pin200_10nm", 0.2, 10), ("laser_5mW", 0, 0)):
        m = cb.budget(d, 100.0, fw)
        assert m["P_at_dmd_uW"] == pytest.approx(rows[case]["P_at_dmd_uW"], rel=0.01)


def test_verdicts_match_led_study_sims():
    chk = cb.sim_check()
    assert len(chk) == 7 and all(v["agree"] for v in chk.values()), chk


def test_light_and_blur_depend_only_on_theta():
    a, b = cb.budget(0.05, 100.0, 10), cb.budget(0.10, 200.0, 10)
    for k in ("P_at_dmd_uW", "smear_spatial_mm", "depth_ratio_R"):
        assert a[k] == pytest.approx(b[k])


def test_monotone_tradeoff():
    rs = [cb.budget(d, 100.0, 10) for d in (0.025, 0.05, 0.1, 0.2)]
    assert all(x["P_at_dmd_uW"] < y["P_at_dmd_uW"] for x, y in zip(rs, rs[1:]))
    assert all(x["depth_ratio_R"] < y["depth_ratio_R"] for x, y in zip(rs, rs[1:]))


def test_frontier_rows_earn_their_target():
    for r in cb.frontier():
        if r.get("pinhole_mm") is not None:
            assert r["verdict"] == r["target"], r
    th = cb.theta_max(cb.R_SEP, 30.0)
    assert th is None                                   # 30 nm spectral smear alone breaks clean separation
    assert cb.theta_max(cb.R_PARTIAL, 0.0) == pytest.approx(cb.R_PARTIAL * cb.DZ_LAYER * cb.na_short(cb.ZS[1]) / cb.ZS[1])
    assert math.isfinite(cb.collimator_min_f()) and cb.collimator_min_f() < 100.0
