"""Scene windows live in the case config, and moving them there changed no frame (BACKLOG offline 3).

Golden snapshot: SHA-256 of every scene's frame at 4 times across its period, recorded from the code as it was
BEFORE the windows moved out of vol2/volplay.py (Volume from configs/case_fit_tank_v4.json, mode "ab", the
bundled duty curve and warp map, no runs/). Matching hashes = byte-identical frames. [PROVED as arithmetic]
Re-record only for an intended change of a scene's output, from the repo root:
  python tests/test_scene_config.py --record
Moved case: a case file whose windows and rows are shifted moves the lit columns and rows with them, so a new
case position needs a new case file, not a code edit. [PROVED as simulation of the DMD frames only]
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))                       # run as a script: import this checkout's vol2

from vol2 import volplay as vp  # noqa: E402

GOLDEN = Path(__file__).with_name("golden") / "scene_frames_v4.json"
CASE_JSON = ROOT / "configs" / "case_fit_tank_v4.json"
N_TIMES = 4


def frame_hashes(vol, lut, scene):
    """SHA-256 of the frames at N_TIMES evenly spaced times over the scene's period."""
    fn = vp.scene_fn(vol, scene)
    ts = np.linspace(0, vp.PERIODS[scene], N_TIMES, endpoint=False)
    return [hashlib.sha256(np.ascontiguousarray(vol.frame(fn(t), lut)[0]).tobytes()).hexdigest() for t in ts]


@pytest.fixture(scope="module")
def lut():
    return vp.load_duty_lut(vp.BUNDLED / "duty_roi.json")


@pytest.fixture(scope="module")
def vol():
    return vp.Volume(str(CASE_JSON))


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))["frames"]


def test_golden_covers_every_scene(golden):
    assert set(golden) == set(vp.SCENES), "re-record the golden snapshot for new or removed scenes"


@pytest.mark.parametrize("scene", sorted(vp.SCENES))
def test_scene_frames_match_golden(scene, vol, lut, golden):
    assert frame_hashes(vol, lut, scene) == golden[scene], f"{scene}: frames differ from the recorded snapshot"


def test_case_file_sections_are_split_from_case_fields(tmp_path):
    """A case file carries its scene windows next to the fit; every loader gets Case fields only, and a misspelt
    field still fails instead of being dropped."""
    from vol2.geometry import Case, load_case_json
    p = tmp_path / "case.json"
    p.write_text(json.dumps({"D": 480.0, "rows": [850, 1095], "scene_windows": {"clean_A": [588, 643]}}))
    over, extra = load_case_json(p)
    assert over == {"D": 480.0, "rows": (850, 1095)} and extra == {"scene_windows": {"clean_A": [588, 643]}}
    Case(**over)
    p.write_text(json.dumps({"D": 480.0, "r_coner": 12}))
    with pytest.raises(TypeError, match="r_coner"):
        Case(**load_case_json(p)[0])


def test_shipped_windows_sit_inside_the_fitted_faces():
    from vol2.geometry import load_case_json
    over, extra = load_case_json(CASE_JSON)
    w = extra["scene_windows"]
    (a0, a1), (b0, b1), (f0, f1) = w["clean_A"], w["clean_B"], w["full_width"]
    (pa0, pa1), (pb0, pb1) = over["planeA_cols"], over["planeB_cols"]
    assert pa0 <= a0 < a1 <= pa1 < pb0 <= b0 < b1 <= pb1, "clean windows inside the fitted face columns"
    assert f0 <= a0 and b1 <= f1, "the full width spans both faces and the corner"


# The scenes that light scene windows. A moved window or liquid moves each of them as a whole, except where a
# wave is phased on the absolute position: ocean_* and fw_ripple on the column, wave_A / waves_AB on the row.
WINDOW_SCENES = sorted(s for s in vp.SCENES if s.startswith(("wave", "ribbon", "ocean", "plane_", "fw_")))
RIGID_COLS = [s for s in WINDOW_SCENES if not s.startswith("ocean") and s != "fw_ripple"]
RIGID_ROWS = [s for s in WINDOW_SCENES if s not in ("wave_A", "waves_AB")]
# even shifts: np.round rounds half to even and the window centres / mid row sit on .5, so an odd shift could
# move a centre by one
D_COL, D_ROW = 6, -20


def _case_file(tmp, d_col=0, d_row=0, drop_windows=False):
    """configs/case_fit_tank_v4.json with its scene windows moved d_col columns and its rows d_row rows."""
    case = json.loads(CASE_JSON.read_text(encoding="utf-8-sig"))
    case["rows"] = [r + d_row for r in case["rows"]]
    case["scene_windows"] = {k: [c + d_col for c in v] if isinstance(v, list) else v
                             for k, v in case["scene_windows"].items()}
    if drop_windows:
        del case["scene_windows"]
    p = Path(tmp) / f"case_{d_col}_{d_row}_{int(drop_windows)}.json"
    p.write_text(json.dumps(case, indent=1))
    return p


@pytest.fixture(scope="module")
def moved_cols(tmp_path_factory):
    return vp.Volume(str(_case_file(tmp_path_factory.mktemp("case"), d_col=D_COL)))


@pytest.fixture(scope="module")
def moved_rows(tmp_path_factory):
    return vp.Volume(str(_case_file(tmp_path_factory.mktemp("case"), d_row=D_ROW)))


def _lit(f, axis):
    """Lit columns (axis 0) or rows (axis 1) of a frame, any channel."""
    return np.nonzero(f.any(2).any(axis))[0]


def _frames(v, scene, lut, phases=(0.0, 0.3)):
    """Frames at these fractions of the scene's period (t = 0 included: sin = 0 puts curtain centres on .5)."""
    fn = vp.scene_fn(v, scene)
    return [v.frame(fn(k * vp.PERIODS[scene]), lut)[0] for k in phases]


def test_case_file_windows_reach_the_volume(vol, moved_cols):
    assert vol.window("clean_A") == (588, 643) and vol.window("full_width") == (560, 785)
    assert moved_cols.window("clean_B") == (697 + D_COL, 748 + D_COL)


@pytest.mark.parametrize("scene", WINDOW_SCENES)
def test_moved_case_file_moves_the_lit_columns_and_rows(scene, vol, moved_cols, moved_rows, lut):
    """Windows moved D_COL columns move every lit column D_COL; liquid rows moved D_ROW move every lit row D_ROW."""
    fa = _frames(vol, scene, lut)
    assert any(len(_lit(a, 0)) for a in fa), "scene lights nothing"
    for a, b in zip(fa, _frames(moved_cols, scene, lut)):
        assert np.array_equal(_lit(b, 0), _lit(a, 0) + D_COL), "lit columns follow the windows"
        if scene in RIGID_COLS:
            assert np.array_equal(b, np.roll(a, D_COL, 1)), "the whole frame moves with the windows"
    for a, b in zip(fa, _frames(moved_rows, scene, lut)):
        assert np.array_equal(_lit(b, 1), _lit(a, 1) + D_ROW), "lit rows follow the liquid"
        if scene in RIGID_ROWS:
            assert np.array_equal(b, np.roll(a, D_ROW, 0)), "the whole frame moves with the liquid"


def test_scenes_without_windows_refuse_and_the_rest_still_play(tmp_path, lut):
    v = vp.Volume(str(_case_file(tmp_path, drop_windows=True)))
    for s in ("ribbon", "wave_A", "ocean", "plane_flat", "fw_static"):
        with pytest.raises(ValueError, match="scene_windows"):
            vp.scene_fn(v, s)
    for s in ("sphere_round", "fwc_static"):                 # pose-fit solids and warp-map planes need no windows
        assert v.frame(vp.scene_fn(v, s)(0.0), lut)[0].any()
    v.windows = {"clean_A": [643, 588], "full_width": [560, 912]}
    for k in ("clean_A", "full_width"):
        with pytest.raises(ValueError, match=k):
            v.window(k)


def test_subframe_build_follows_the_case_file(tmp_path, monkeypatch):
    """vol2.subframe build --case-json: the packed 1440 Hz frame moves with the windows too (writes files only)."""
    import cv2

    from vol2 import subframe
    monkeypatch.setattr(subframe, "OUT", tmp_path / "subframe")
    cols = []
    for case in (CASE_JSON, _case_file(tmp_path, d_col=D_COL)):
        out = subframe.build("plane_flat", seconds=1 / 60, case_json=case)
        cols.append(_lit(cv2.imread(str(out / "frames" / "f0000.png"), cv2.IMREAD_COLOR), 0))
    assert len(cols[0]) and np.array_equal(cols[1], cols[0] + D_COL)


def record():
    """Write the golden file from the current code (bundled calibration only: runs/ is pointed elsewhere)."""
    import os
    import tempfile

    from rig import config
    os.environ["DLP_NO_HARDWARE"] = "1"
    with tempfile.TemporaryDirectory() as tmp:
        config.RUNS = Path(tmp) / "runs"                 # no bench runs: bundled duty curve and warp map
        lut = vp.load_duty_lut(vp.BUNDLED / "duty_roi.json")
        vol = vp.Volume(str(CASE_JSON))
        frames = {s: frame_hashes(vol, lut, s) for s in sorted(vp.SCENES)}
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "note": "SHA-256 of vol2.volplay frames (1140x912x3 uint8, C order) at t = k/4 of each scene's period, "
                "k = 0..3; Volume(configs/case_fit_tank_v4.json), mode ab, bundled duty curve and warp map. "
                "Recorded before the scene windows moved into configs/. See tests/test_scene_config.py.",
        "numpy": np.__version__, "frames": frames}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{GOLDEN}: {len(frames)} scenes")


if __name__ == "__main__":
    if sys.argv[1:] != ["--record"]:
        raise SystemExit("usage: python tests/test_scene_config.py --record")
    record()
