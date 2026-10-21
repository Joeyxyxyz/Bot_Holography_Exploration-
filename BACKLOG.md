# Backlog

**Offline** items need no hardware, so a cloud session can do them. **Bench** items need Joey at the rig: an AI session can prepare the code and the exact commands, and Joey runs them. Details and numbers are in `docs/BRIEFING.md` §7.

## Offline

1. **Held-out calibration check.**
   - Predict the warp-scan dot positions (`data/calibration/warp_scan/`) from the fitted case geometry (`configs/case_fit_tank_v4.json`) and the ray model, then report the error.
   - Today the fit is exactly determined: 2 edges, 2 free parameters, D unconstrained. This would be its first independent test.
2. **Model the inverted case.**
   - On 2026-10-05 the case was upside down: clear acrylic floor, black base overhead.
   - Add floor reflections to `vol2/geometry.py`, then re-run the joint-region estimates.
3. **Move hard-coded column windows into config.**
   - The curtain, plane and `fw_*` windows in `vol2/volplay.py` are DMD columns for one case position.
   - Derive them from `configs/` so that a moved case needs only a re-map.
4. **A content planner that knows about ghosts.**
   - Choose rod and band sets that maximise on-shape light and minimise ghost crossings, using `vol2/simulate.py` as the metric.
   - Start from the "woven box" result (8 real corners, 0 ghosts).
5. **Round cross-sections.**
   - Simulate face-A light reflected off the bare back wall: it runs at about 90° to face B.
   - Weigh rounder shapes against the extra crossings.
6. **1440 Hz sub-frames.**
   - The 24-plane pack / unpack round trip is already tested (`tests/test_vol2.py`).
   - Still untested: `vol2/subframe.py`'s slot spread (`_ORDER`), the duty thresholds (round(24·d) slots lit), `raster_binary`, and `build()` output.
   - Write a simulated preview of what the eye integrates.
7. **New scenes.**
   - Add scenes in the style of the ribbons, which looked best by eye, plus any scene `volplay` lacks.
   - Each needs a test in `tests/test_scenes.py` and a `--dry` render.
   - `ocean` and `ocean_storm` loop every 10 s, but face B's waves don't repeat in 10 s, so the loop has a visible jump. Give face B whole cycles per loop, or document the jump.
8. **Viewer-independent warp.**
   - Today's correction holds for one camera position only.
   - Model the rounded-edge lensing so that a correction can be predicted for another viewpoint.
9. **Holography simulation (still simulation only).**
   - Extend `holo/` to show what a coherent build would need: LED with pinhole and collimator onto the bare DMD.
   - Report light budget and depth separation.
10. **STOP for capture sessions.**
    - Today only the players and holds watch `STOP`. Make `Bench.shoot` raise a clean "stopped" exception when `STOP` exists, so any rig session can be ended the same way, and update SAFETY.md.
11. **Code health.**
    - Add a ruff lint step to CI and type hints on the public functions in `vol2/`.
    - Write a short `docs/ARCHITECTURE.md` for the ray model.
12. **Holo Studio: "make your own".**
    - Add a panel where people shape a scene themselves:
      - ribbon turns, speed and count;
      - plane height, thickness and motion;
      - ball size and motion.
    - Build it from parametric versions of the existing scene families in `vol2/volplay.py`. Keep the current scene names and output byte-identical (golden test).
    - Save and load named playlists.

## Bench (Joey runs; prepare the commands)

- **Pre-flight before any warp-corrected scene:**
  - Re-project the numbered grid, or re-run the column sweep.
  - The silhouettes should sit at about cols 583 / 764.
- **Measure the absorption length L.** The player assumes 30 mm [HEURISTIC].
- **Extend the warp scan** to the outer edges with a denser scan near cols 560–610 and 750–785. Flag dots that fall outside the case.
- **Log playback** for the `fw_*` / `fwc_*` scenes. Check DMD-side timing with a photodiode or a high-speed camera.
- **Stereo capture** from two camera positions, to record 3D form. Capture the ribbon-only scenes, which have no images yet.
- **1440 Hz video-port pattern mode.** The GUI mode switch is Joey's. Compare it with 60 Hz.
- **Re-run the duty calibration** (`python -m vol2.calib_duty duty`) after any LED, fill or dye change.
- **First live run of Holo Studio:**
  - Set the DMD display to a plain black desktop, then run `python -m studio`.
  - Play `Thick plane` for 10 s, press STOP partway through, then check that the scanner can take the rig right away.
