"""Scene windows live in the case config, and moving them there changed no frame (BACKLOG offline 3).

Golden snapshot: SHA-256 of every scene's frame at 4 times across its period, recorded from the code as it was
BEFORE the windows moved out of vol2/volplay.py (Volume from configs/case_fit_tank_v4.json, mode "ab", the
bundled duty curve and warp map, no runs/). Matching hashes = byte-identical frames. [PROVED as arithmetic]
Re-record only for an intended change of a scene's output, from the repo root:
  python tests/test_scene_config.py --record
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
