"""FLIR Blackfly S (BFS-U3-16S2M, mono) via PySpin, free-running. Leftover state from other programs
(ROI, binning, mirroring, gamma, frame-rate cap, trigger) is reset best-effort; buffers are NewestOnly so the
first grab after a projector hold is a fresh frame."""
from __future__ import annotations

import numpy as np

GRAB_TIMEOUT_MS = 2000
INCOMPLETE_RETRIES = 3


class Camera:
    def __init__(self, exposure_us: float, gain_db: float = 0.0):
        from .safety import check_hardware_allowed
        check_hardware_allowed()
        import PySpin  # noqa: F401 - hardware extra; not needed for anything offline
        self._ps = PySpin
        self._sys = PySpin.System.GetInstance()
        self._list = self._sys.GetCameras()
        if self._list.GetSize() == 0:
            self._list.Clear()
            self._sys.ReleaseInstance()
            raise RuntimeError("No FLIR camera found (check the USB3 cable).")
        self._cam = None
        try:
            self._cam = self._list.GetByIndex(0)
            self._cam.Init()
            self._reset()
            self._cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            self.set_exposure_us(exposure_us)
            self._cam.GainAuto.SetValue(PySpin.GainAuto_Off)
            self._cam.Gain.SetValue(float(gain_db))
            self._cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
            self._cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            self._cam.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)
            self._cam.BeginAcquisition()
            for _ in range(3):                        # warm-up frames
                self.grab()
        except BaseException:
            self.close()
            raise

    def _reset(self):
        ps, c = self._ps, self._cam
        steps = [lambda: c.TriggerMode.SetValue(ps.TriggerMode_Off),
                 lambda: c.BinningHorizontal.SetValue(1), lambda: c.BinningVertical.SetValue(1),
                 lambda: c.OffsetX.SetValue(0), lambda: c.OffsetY.SetValue(0),
                 lambda: c.Width.SetValue(c.Width.GetMax()), lambda: c.Height.SetValue(c.Height.GetMax()),
                 lambda: c.ReverseX.SetValue(False), lambda: c.ReverseY.SetValue(False),
                 lambda: c.GammaEnable.SetValue(False), lambda: c.AcquisitionFrameRateEnable.SetValue(False)]
        for s in steps:
            try:
                s()
            except Exception:  # noqa: BLE001 - node missing or locked on this model: best effort
                pass

    def set_exposure_us(self, us: float) -> None:
        self._cam.ExposureTime.SetValue(float(us))

    def grab(self) -> np.ndarray:
        for _ in range(1 + INCOMPLETE_RETRIES):
            img = self._cam.GetNextImage(GRAB_TIMEOUT_MS)
            try:
                if not img.IsIncomplete():
                    return img.GetNDArray().copy()
            finally:
                img.Release()
        raise RuntimeError("camera delivered incomplete frames repeatedly: USB3 bandwidth / cable")

    def flush(self) -> None:
        self.grab()

    def close(self) -> None:
        """Idempotent; also cleans up after a failed open (camera busy, USB error)."""
        cam, self._cam = getattr(self, "_cam", None), None
        if cam is not None:
            try:
                if cam.IsStreaming():
                    cam.EndAcquisition()
            except Exception:  # noqa: BLE001
                pass
            try:
                cam.DeInit()
            except Exception:  # noqa: BLE001
                pass
            del cam                                   # PySpin: drop the camera before releasing the system
        if getattr(self, "_list", None) is not None:
            self._list.Clear()
            self._list = None
        if getattr(self, "_sys", None) is not None:
            self._sys.ReleaseInstance()
            self._sys = None
