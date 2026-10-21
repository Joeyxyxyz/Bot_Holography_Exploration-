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
   - Tested offline (`tests/test_vol2.py`, `tests/test_subframe.py`):
     - the 24-plane pack / unpack round trip, and the plane-check digit k in slot k;
     - the slot spread (`_ORDER`): a growing duty lights slots 0, 12, 6, 18, 3, 15, …;
     - the duty rule: round(24·d) slots lit, an exact half rounds down, and a higher duty only adds slots;
     - `raster_binary`, slot k sampled at t + k/1440, and `build()` output;
     - an all-zero-duty sub-frame, and an all-zero-duty 60 Hz frame (`Volume.frame`), stay dark: no 0 / 0 renormalisation.
   - Simulated preview: `python -m vol2.subframe preview <scene> [--frame i]` [PROVED, simulation].
     - It averages a packed frame's 24 slots and compares them with the 60 Hz frame of the same instant (t = i/60).
     - Every scene at frames 0, n/4, n/2 and 3n/4 of its loop (2026-10-20):
       - Static scenes agree to within half a slot (1/48) plus the 60 Hz level rounding: max |diff| 0.022 (`sphere_round`).
       - Moving scenes smear across the frame (max |diff| up to 0.96).
       - Total light (glow sum, 1440 / 60 Hz): within 1% in 106 of 118 samples of 30 moving scenes, but 0.940 to 1.069 overall. The outliers are `fw_breathe` (0.940), `orbit` (0.968 and 1.032), `fw_split` (1.069) and `sphere_pulse` (1.018). Not analysed yet.
       - `fw_stack` and `fwc_stack` frame 0: the 60 Hz frame is empty while slots 22 and 23 already light, so there is no ratio.
     - It assumes every lit slot adds the same glow. That is not measured.
   - Open: the duty is renormalised per sub-frame (and per 60 Hz frame in `volplay`), so changes of duty over time are normalised away.
     - `ball_pulse` renders the same at duty 0.35 and 1.0. The duty breathing of `fw_breathe` and `sphere_pulse` (their size still changes) and the final fade of `fw_stack` are lost the same way.
     - Normalising over the whole loop would fix it, but it changes what the 60 Hz player shows. Joey decides.
7. **New scenes.**
   - Add scenes in the style of the ribbons, which looked best by eye, plus any scene `volplay` lacks.
   - Each needs a test in `tests/test_scenes.py` and a `--dry` render.
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
