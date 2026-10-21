"""Every test runs with hardware forbidden, a private rig lock and private STOP files: the tests can never open
the DMD window or the camera, never touch the machine-wide lock another program may hold, and never stop (or
leave a STOP file for) a real player."""
import pytest

from rig import bench, config
from vol2 import volplay


@pytest.fixture(autouse=True)
def no_hardware(monkeypatch, tmp_path):
    monkeypatch.setenv("DLP_NO_HARDWARE", "1")
    monkeypatch.setattr(config, "LOCK_PATH", tmp_path / "rig.lock")
    monkeypatch.setattr(config, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(config, "STOP", tmp_path / "STOP")
    monkeypatch.setattr(config, "STOPALL", tmp_path / "STOPALL")
    monkeypatch.setattr(volplay, "STOP", tmp_path / "STOP")
    monkeypatch.setattr(bench, "OUT", tmp_path / "runs")
    yield
