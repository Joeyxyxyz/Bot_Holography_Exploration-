"""Every test runs with hardware forbidden and a private rig lock: the tests can never open the DMD window or
the camera, and never touch the machine-wide lock another program may hold."""
import pytest

from rig import bench, config


@pytest.fixture(autouse=True)
def no_hardware(monkeypatch, tmp_path):
    monkeypatch.setenv("DLP_NO_HARDWARE", "1")
    monkeypatch.setattr(config, "LOCK_PATH", tmp_path / "rig.lock")
    monkeypatch.setattr(config, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(bench, "OUT", tmp_path / "runs")
    yield
