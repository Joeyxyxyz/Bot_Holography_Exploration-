"""Two-face (corner-on, right side up) re-map: grid shot, floods, column sheets, row lines. Blue HDMI only.
  python -m vol2.twoface_map capture
"""
import json, sys, time
from pathlib import Path
import cv2, numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
H, W = 1140, 912
COLS = (540, 800, 2); COL_ROWS = (700, 985); ROWS = (700, 984, 6); ROW_COLS = (540, 800)

def frames():
    out = [("black_0", np.zeros((H, W), np.uint8))]
    g = cv2.imread(str(ROOT / "runs" / "20261005T072131_numgrid_wide" / "dmd_numgrid.png"), 0)
    out.append(("grid", np.where(g > 127, 255, 0).astype(np.uint8)))
    f = np.zeros((H, W), np.uint8); f[700:985, 540:800] = 255; out.append(("flood", f))
    out.append(("black_1", np.zeros((H, W), np.uint8)))
    for c in range(COLS[0], COLS[1] + 1, COLS[2]):
        f = np.zeros((H, W), np.uint8); f[COL_ROWS[0]:COL_ROWS[1], c:c + 2] = 255; out.append((f"col_{c}", f))
    out.append(("black_2", np.zeros((H, W), np.uint8)))
    for r in range(ROWS[0], ROWS[1] + 1, ROWS[2]):
        f = np.zeros((H, W), np.uint8); f[r:r + 3, ROW_COLS[0]:ROW_COLS[1]] = 255; out.append((f"row_{r}", f))
    out.append(("black_3", np.zeros((H, W), np.uint8)))
    return out

def capture(exp=66667):
    from rig import bench as vm
    fr = frames()
    run = vm.OUT / (time.strftime("%Y%m%dT%H%M%S") + "_twoface_map"); run.mkdir(parents=True)
    vm.DUTY = 1.0
    lock, sync = vm.open_rig(); shots = {}
    try:
        sync.camera.set_exposure_us(exp)
        for name, f in fr:
            shots[name] = sync.shoot(np.dstack([f, f * 0, f * 0]).astype(np.uint8), raw=True).astype(np.float16)
        sync.shoot(np.zeros((H, W), np.uint8))
    finally:
        sync.close(); lock.release()
    np.savez_compressed(run / "raw.npz", **shots)
    g = np.clip(shots["grid"].astype(np.float32) - shots["black_0"].astype(np.float32), 0, None)
    cv2.imwrite(str(run / "grid_cam.png"), (np.clip(g / max(np.percentile(g, 99.8), 1), 0, 1) ** 0.6 * 255).astype(np.uint8))
    (run / "meta.json").write_text(json.dumps({"exposure_us": exp, "cols": COLS, "col_rows": COL_ROWS, "rows": ROWS,
        "row_cols": ROW_COLS, "setup": "case right side up, corner-on, two faces lit (Joey 20:46)"}, indent=1))
    print(run, flush=True)

if __name__ == "__main__":
    capture()
