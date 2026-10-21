# Briefing: volumetric projection into a fluorescent acrylic case with a DLP LightCrafter 4500

**For:** Grok. **From:** Joey's DMD-experiments session with Claude, covering 2026-09-29 and 2026-10-05.
**Scope:** everything done in those two sessions, what worked, what didn't and why, and how to run it.
**Checked:** independently fact-checked against the bundled data before packaging; corrections are applied.
**This copy:** the briefing as packaged on 2026-10-05, with paths updated to this repository's layout. Raw camera runs and the design-panel folder are not in the repo.

**Tags:**
- [PROVED]: measured here, or arithmetic / simulation explicitly stated as such.
- [ASSERTED]: standard physics or vendor data.
- [HEURISTIC]: judgement, a visual read, or a placeholder model.

**Paths:** relative to the repository root.
- `docs/LAB_LOG.md` is the running log (formerly `HOLO_PLAN.md`). Despite its name, it covers the stock-projector two-plane work: sections A.1–A.8, with A.6a–g for 2026-10-05.
- Some early numbers in A.2, A.5 and A.8 are superseded by A.6.

---

## 0. TL;DR

- **Setup.** A stock DLP LightCrafter 4500 projects through HDMI, blue only, into a small acrylic case filled with glycerin and yellow highlighter ink (fluorescein). The case stands corner-on, so the projector reaches the liquid through two faces, A and B. Every lit mirror becomes a glowing line (a "ray") through the liquid.
- **Two ray families.** The light entering through face A and through face B crosses inside the case at about 30° in glycerin (model value, never measured directly; see §3). Content is built from those rays.
- **What Joey liked best by eye** (no camera proof of 3D form, see below):
  1. **ribbons**, twisting light curtains, best structure and animation;
  2. **thick blue planes** spanning the full width;
  3. **solid shapes** made of crossing filled bands;
  4. **"string-art" layer stacks** such as a pyramid and a diamond.
- **The player.** `vol2/volplay.py` drives everything with a measured duty (brightness) curve. Its software push loop held 59.9–60.0 frames/s, with 0–4 late frames in each of the 21 scenes that were logged.
- **Distortion.** The case bends the projection, worst at face A and the rounded edges. A dot-grid scan measured it. A per-column correction made a flat plane level and about 2.5× straighter, **as seen from this camera, over DMD columns 610–750**.
- **Hard limits** of a linear glowing medium:
  - Every lit ray glows along its whole path, so a crossing is at most 2× as bright.
  - Points sharing a height create ghost crossings, and horizontal lines light whole planes.
  - Fast time-multiplexing doesn't remove ghosts: the eye adds up light over time.
  - True floating voxels need a moving screen (Geng 2013) or a two-step medium.
- **Holography.** No hardware holographic reconstruction was attempted. In simulation only, an LED with a 75 µm pinhole partly reconstructs a 3-layer hologram, at 0.06–0.6 % of the bare-LED light. Through the stock lens there is no holographic depth.

---

## 1. Glossary

| Term | Meaning | Where defined |
|---|---|---|
| DMD col / row | Mirror column (0–911) and row (0–1139) of the 912 × 1140 HDMI frame, shown 1:1 on the mirrors. Rows are half-pitch (diamond array). | `rig/config.py` |
| Face A / face B | The two case faces the projector lights while the case is corner-on. A = toward the camera, B = toward the projector side. | `configs/case_map_tank_v2.json` |
| Corner | The rounded vertical edge between A and B. It smears and bends light. | same |
| Plane A / plane B ("families") | The rays entering through face A / face B. Inside the liquid each family is a near-horizontal fan. | `vol2/geometry.py` |
| Crossing | Where an A ray and a B ray meet: ≤ 2× brightness. | `render.py pair()` |
| Joint region / joint box | Where both families reach. The joint box is its largest square in plan view. | `render.py joint_box()` |
| qa, qb | Plan coordinates in mm, along face A and face B from the outer corner. | `geometry.py` |
| cpm / rpm | DMD columns / rows per mm at the corner distance D (scale of the pinhole model). | `Case` dataclass |
| psi | Case rotation about vertical (0 = corner-on). | `Case` |
| Duty | An element's share of full glow (0–1), sent as a blue level through the measured curve. | `volplay.py`, `data/calibration/duty_roi.json` |
| Rod / band / curtain | One mirror block = one glowing ray at one height (rod). Many adjacent rods at one height = a band. One column per row = a sheet (curtain). | `rods.py`, `solid.py`, `volplay.py` |
| TIR leg | Light totally reflected off a wall back into the liquid. | `geometry.py trace()` |
| Warp map / correction | Measured camera position of each scanned mirror, and the per-column row shift that makes a plane look straight. | `warp_scan.py`, `data/calibration/warp_scan/warp_map.*` |

**Coordinates:** world mm, with the projector pinhole at the origin, **y down**, x to the right as seen from the projector, z away from it.

**Top view of the 2026-10-05 layout** [HEURISTIC]:
```
            projector (moved back, >= 0.5 m)
                 |
                 v
              /\        <- corner (DMD col 11, cols 656-684)
     face A  /  \  face B
 (cols 544-656)  (cols 684-768)
           \    /
            \  /        back walls (bare acrylic)
camera  ->   \/   (camera left of the projector, looking roughly straight through face A)
```

---

## 2. Hardware and setup

- **Projector:** TI DLP LightCrafter 4500, EKB "4500 MKII" build (DLPC350; DLP4500 DMD, 912 × 1140, diamond array, 10.8 µm column pitch and 5.4 µm row pitch). Stock RGB LEDs and stock lens: F/2.1, throw 1.4, 100 % vertical offset, **focus range 0.5–2 m** (TI DLPU011E Table 1-1) [ASSERTED].
  - Driven as an HDMI monitor: 912 × 1140 at desktop position (1920, 0), video mode.
  - **Colour comes only from the HDMI frame** (blue-only frames light only the blue LED sub-frames). LED currents were never changed (bench R35 G50 B45).
- **Camera:** FLIR Blackfly S BFS-U3-16S2M, mono. The lens is zoomed onto the case. It sits left of the projector and looks roughly straight through face A.
  - **No long-pass filter**, so every "glow" number is fluorescence plus scattered or reflected light.
- **Case:** 63.1 mm square at the base and 60.1 mm at the top, 72.95 mm tall acrylic with rounded vertical edges, on a 22.35 mm black base.
  - **On 2026-10-05 it was upside down** (black base on top). Fill: glycerin + yellow highlighter. The back walls are bare acrylic.
  - Bench record: `configs/setup_tank_v2.json`. Distances were not re-measured that day.
- **Geometry, 2026-10-05:** Joey's call-outs from a projected numbered grid (`configs/case_map_tank_v2.json`). The case spans grid cells 7–14 × E–M.

  | Region | Grid column | DMD columns |
  |---|---|---|
  | Face A | 7–10 | 544–656 |
  | Corner | 11 | 656–684 |
  | Face B | 12–14 | 684–768 |

- **Model geometry** (`configs/case_fit_tank_v4.json`): all mm-scale numbers in this briefing depend on it.

  | Field | Value | Source |
  |---|---|---|
  | col_corner | 670 | Joey's call-out (col 11 centre) |
  | cpm | 2.36 | fitted (see §3, calibration) |
  | psi | +2° | fitted |
  | D | 480 mm | **unconstrained** (fit is identical for 430–530) |
  | rpm | 5.0 | placeholder (≈ 2.1 × cpm, the diamond ratio) |
  | row_ref / row_base / fill_mm | 970 / 1095 / 49 | hand / row-sweep edges [HEURISTIC] |
  | r_corner | 12 mm | hand, after Joey saw corner bending |
  | planeA_cols / planeB_cols | 584–645 / 695–750 | hand, from the scans and Joey's corner observation |

  - **Unknowns:** projector pitch / principal point, the diamond row-parity offset, and absorption length.
  - **Upside-down caveat.** The ray model still assumes an absorbing floor (the black base) and a free liquid surface on top. With the case inverted, the floor is clear acrylic and the black base is overhead. Floor reflections are not modelled, so reflected legs near the bottom and the joint-region estimates near the floor may be off [HEURISTIC].
- **Rig rules** (must be kept by anyone driving the bench):
  - One program at a time, through the machine-wide **rig lock** (`rig/lock.py`, shared with the swiss-army-scanner).
  - HDMI video mode only. **No USB/HID commands** to the DLPC350 and **no LED current changes** from code.
  - Pattern-sequence / flash mode is Joey's, in the **EKB 4500 MKII GUI**, after a firmware backup.
  - Physical steps are Joey's.
- **Kickoff status** (the project kickoff; not included here):
  - E0 done: `ogr.validate` 31/31 on the OGR math package (vendored as `third_party/OGR_DMD_MathPackage_v1.0`).
  - E1–E3 (scanner photon isolation) not done here: Joey redirected to volumetric projection.
  - E4: offline T2–T4 done; no coherent hardware.
  - E5 not done.

---

## 3. What was done, in order

### 2026-09-29 (empty case, then water)
1. **OGR package check:** `python -m ogr.validate` → **31/31** [PROVED].
2. **Empty-case mapping:**
   - A Gray-code sweep showed the finest bits below camera resolution.
   - The multi-frequency phase scan gave ~503 k valid pixels.
   - The wall polynomial fit left 0.08 mirror residual.
   - A cube projected at the empty case landed on the wall and back face (`docs/figures/01_…`).
3. **Holography, offline** (`holo/`, reports in `data/results/hologram_*`), simulation only:
   - **T2 sweep:** reproduces 0.977 at f_c = fill = 0.125, and fails when fill > 1.33 f_c.
   - **Lensless Fresnel cube:** 3 layers at 0.38 / 0.40 / 0.42 m, 532 nm. The focus stack separates the front and back faces in simulation (`docs/figures/02_…`).
   - **LED coherence** (`docs/figures/03_…`, `data/results/hologram_led_study.json`):
     - A 75 µm pinhole partly separates the near and middle layers, at 0.06–0.6 % of the bare-LED light depending on the filter. The far layer fails.
     - 200 µm gives no depth separation; 500 µm and the bare die wash out [HEURISTIC, simulation only].
   - **Stock lens:** magnification M ≈ 37–40 at the case (0.40–0.43 mm per DMD column ÷ 10.8 µm). Angles shrink by M, so axial resolution 2λ/NA² grows ~M² → roughly 0.6–0.7 m: no holographic depth in a 60 mm case [HEURISTIC scaling].
4. **Lean files reviewed:**
   - `output88_cube_projection` holds constants only.
   - `output92_signed_depth_multiplexing`: its signed-carrier depth conflicts with the OGR corrections.
   - The kinetic/thermal ledger is unrelated.
5. **Two-plane ray model** (`vol2/`): vector Snell through the walls, then rays in the liquid.
   - A 9-agent adversarial review found **total internal reflection at the back walls**: model ~2/3 of rays in water, ~57 % in glycerin. TIR legs were added.
   - It also found the calibration was cell-quantised, so a calibration sweep was built.
6. **Clear water:** no visible in-liquid light even with all mirrors on at 0.2–0.5 s [PROVED for clear water; ASSERTED for clear liquids generally]. Hence the fluorescent fill.

### 2026-10-05 (glycerin + highlighter, case upside down)
1. **Flood:** the whole liquid glows from either face (`docs/figures/04_…`).
2. **Calibration:**
   - **Column sweep:** each column is a glowing sheet. Silhouette edges at cols **583.4 / 764.2** (`data/results/calib_sweep_v2.json`, plot `data/results/calib_sweep_v2_profiles.png`).
   - **The automatic fit failed:** corner 698, cpm 2.46, psi at the −12° search bound, residual 4.1 col, in that same JSON.
   - **Manual refit** with the corner fixed at Joey's col 11 (670): **cpm 2.36, psi +2°, residual 0.47 col** (`data/results/calib_fit_fixed_corner.json`). This is [HEURISTIC]: 2 edges against 2 free parameters, exactly determined, D unconstrained. No held-out check yet.
   - **Contact sheet** (`docs/figures/05_…`): by eye, face-A columns ~582–654 look like clean sheets and the corner smears ~660–678 [HEURISTIC, visual]. The per-column bend metric (`data/results/edge_quality.json`) disagrees for cols ~586–620 (strong centroid bend). Treat "clean" as provisional.
3. **First content** (`docs/figures/06_…`): helix (two zigzags) and cube (box outline with ghost bars).
4. **"String art"** (`docs/figures/07_…`, `08_…`):
   - Each layer is 2 face-A rods + 2 face-B rods, whose 4 crossings are the corners: no ghosts by construction.
   - Pyramid / diamond / sphere / hourglass / cage outlines are recognisable in the camera images [HEURISTIC, visual]. These are **2D silhouettes, largely the entry patterns on face A** (see item 5), not a verified 3D form.
5. **Viewpoint study** (`docs/figures/11_`, `12_`, simulation):
   - The single camera mostly records the **entry points on face A**, because it looks through the input face.
   - Side-on views of a rod stack are stacked lines.
   - One camera integrates along its line of sight and cannot show 3D crossings; eyes (stereo, head motion) can [ASSERTED].
6. **Input B, output A** (Joey's idea):
   - B-only light seen through the unlit face A (`docs/figures/13_…`).
   - **One-face two-family mode:** direct B rays × B rays totally reflected off the back-right wall cross at **58°** in the model (joint box 12.9 mm). Dim on camera (`docs/figures/14_…`).
7. **Beams fade by the centre** (Joey, by eye). Content was moved toward the middle, and the corner keep-out widened after Joey saw corner bending (`case_fit_tank_v4.json`).
   - **Off-corner shapes** at qa = qb = 40 mm (`docs/figures/15_…`): crossings at 2× on full-length rods. Joey: "it's not hitting" the corner now.
8. **Solid shapes** (`docs/figures/16_`, `17_`):
   - Each 1 mm layer is a filled A band × a filled B band, giving a rhombic cross-section at 2×.
   - Cube / ball / pyramid / diamond / cone silhouettes are recognisable on camera [HEURISTIC, visual; two copies per shape, one per face's entry view].
   - The B-only versions are crisp near B's entry and blur into a beam deeper in.
9. **Design panel** (3 independent designs + judge, simulation; the panel folder is not in this repo):
   - Winner: a "woven box": 2 "#" levels, 8 real corners, 0 ghosts.
   - Robust to scale, distance, rotation and pitch error, but **a ±6-column corner error loses 4 of the 8 corners**.
   - Projected once for Joey to view by eye; not photographed. Suggested viewing: behind-left, ~20° above, through a bare back wall.
   - Confirmed limits: no floating cube (~80 % of the light lies off-shape), no drawn vertical edges.
   - `docs/figures/24_…` shows the model's plan-view coverage: blue = A only, orange = B only, white = both.
10. **Speed** (Geng 2013, *Displays* 34:39–48, supplied by Joey):
    - Bit-plane splitting puts 24 one-bit slices in each 24-bit video frame.
    - The DLPC350 supports it natively in Pattern Sequence mode with Video-port source and VSYNC trigger: 1-bit patterns up to 2880 Hz from the video port, 4225 Hz from flash, 235 µs minimum (DLPU011E Table 4-1) [ASSERTED].
    - That gives 1440 sub-frames/s at 60 Hz HDMI.
    - In a linear medium this buys smooth motion and linear duty, not depth gating.
11. **Duty and refresh** (`data/calibration/duty_roi.json`, `data/results/playback_*.json`):
    - **Duty curve,** blue level → relative glow: a dead zone, then ≈ (v/255)^2.6. The player uses the table [PROVED, camera].

      | Level | ≤ 48 | 64 | 96 | 128 | 160 | 192 | 224 | 255 |
      |---|---|---|---|---|---|---|---|---|
      | Glow | ~0 | 0.03 | 0.10 | 0.22 | 0.44 | 0.66 | 0.87 | 1.0 |

    - **Push rate:** the HDMI window loop accepted ~225 pushes/s (console measurement, not saved).
    - **Playback:** 59.9–60.0 frames/s with 0–4 late frames over 25–30 s runs (1500–1801 frames), in the **21 scenes with playback logs**. The fw_* / fwc_* plane scenes have no logged playback stats.
    - These numbers count software pushes on a clock; nothing verified what the DMD displayed (no photodiode) [PROVED for the software loop only].
12. **Scenes, Joey by eye** (no camera capture of the ribbon-only scenes or the rounded spheres; `fw_ribbon`, a plane plus ribbon curtains, was captured: `docs/figures/23_fw_ribbon_camera.gif`):
    - Ribbons were best for structure and animation; other scenes: rippling curtains, ocean waves, flat / sweeping / tilted planes.
    - Spheres look like squashed diamonds: at a ~30° crossing every cross-section is a rhombus ~3.7:1 (≈ 3.5–4.2:1 over 27–32°). Graded duty rounds them off.
13. **Stronger, flatter plane:**
    - **Colour test** (`docs/figures/18_`, `19_`, `data/results/plane_color.json`): total in-band glow relative to blue, **including edge glints**: green 3.6×, cyan 4.5×, white 5.7×, red 1.9×.
      - By eye on the profile plot, the in-liquid baseline is ~2–3× blue for green / white [HEURISTIC]. The rest is glints on the acrylic edges.
      - Blue gives the cleanest plane.
    - **Geometry test** (`docs/figures/20_…`, `data/results/plane_geom.json`, baseline = a 6-row plane on the clean windows only):
      - Full width **with the corner included**: 2.1×. The rounded corner spreads light and fills the gap between the faces.
      - **12 rows thick: 4.3×, evenness 0.61.** Glow scales with lit rows.
      - 40-row slab: 15×.
14. **Distortion scan and correction:**
    - **Dot grid** (`docs/figures/21_…`, `data/calibration/warp_scan/warp_map.*`): 177 / 276 dots located.
      - Over the full scanned width, each DMD row comes out tilted (fitted slope ~0.1) and bowed (RMS ~6 px, max ~11 px).
      - Face B's direct path is the most regular.
      - A's far outer edge throws its dots far left. B's outer edge throws them back toward the middle; some of those may be misses outside the case.
    - **Correction** (`docs/figures/22_…`, `data/results/warp_test.json`): per-column rows over cols 610–750, so the plane lands on one level line in this camera's view. **Viewer-specific** [PROVED, camera].

      | Plane | Slope | RMS | p95 |
      |---|---|---|---|
      | Uncorrected | 0.026 | 3.0 px | 5.4 px |
      | Corrected | 0.003 | 1.2 px | 2.9 px |

      - The 0.026 slope is measured on the projected plane within 610–750; the ~0.1 is the dot-grid row fit across the whole width.
      - Camera scale at the case is roughly 3–4 px/mm [HEURISTIC], so 3.0 → 1.2 px is about 0.9 → 0.35 mm.
    - **Plane animations:** corrected fwc_* and plain fw_*. Camera GIFs in `docs/figures/23_*` (5 fwc_, 3 fw_).

---

## 4. Core physics, compact

| Fact | Status |
|---|---|
| Glow ∝ light passing (linear); a crossing of two equal beams ≤ 2× one beam | [ASSERTED] + simulated |
| n points at one height → n² crossings (ghosts); a horizontal line lights a whole plane (both fans near-horizontal) | [PROVED] geometry |
| Time-multiplexing faster than the eye does not remove ghosts (linear integration) | [ASSERTED] |
| Crossing angle (glycerin): collimated limit 32.5°; traced fan median ~29–30° (range ~27–32° by column pair). Water: 25.9° / ~22°. Never measured. | Snell [PROVED] / model |
| The families' overlap is a wedge opening toward the back corner; clean overlap starts ~35 mm in from the corner on each face | model [HEURISTIC] |
| Back walls: ~57–67 % of rays exceed the critical angle and reflect (≈ 3 mm walk-off) | model, review-confirmed |
| Rounded vertical edges spread a beam into a fan, smear sheets and displace light | [PROVED] camera |
| Fluorescein absorbs blue; beams fade by the centre; green / white carry further but glint | camera + Joey [HEURISTIC for "by the centre"] |
| A single camera cannot show 3D crossings; eyes / stereo can | [ASSERTED] |
| Holographic depth needs spatially coherent light on the bare DMD; the stock lens rules it out | simulation / [HEURISTIC] |

---

## 5. How to run

**Environment:**
- Python 3.10+ with numpy and OpenCV (`pip install -e ".[dev]"`); run from the repository root.
- The bench camera needs PySpin (FLIR Spinnaker SDK). GIF building needs Pillow.
- All hardware access goes through `rig/` (lock, HDMI window, camera). Read `SAFETY.md` first.

**Pre-run check:** re-project the numbered grid (`tools/numgrid.py`, held with `tools/play_loop.py`), or re-run the column sweep. The silhouettes should stay at ~583 / ~764. If they move, re-map before using the fwc_* scenes.

**Offline render, no rig:**
```
python -m vol2.volplay <scene> --dry --case-json configs/case_fit_tank_v4.json
```
Note: the player reads the **latest** `runs/*_duty/duty_roi.json` and (for fwc_*) the latest `runs/*_warp_scan`; with no runs it falls back to the bundled `data/calibration/` copies. A new capture changes every scene's output. The curtain and plane column windows are hard-coded and must be edited if the case moves.

**Play at 60 Hz:**
```
python -m vol2.volplay <scene> --seconds 30
```
Each run takes the rig lock. A file `STOP` ends the current scene; `STOPALL` ends the `tools/demo_planes.ps1` loop.

| Group | Scenes |
|---|---|
| Ribbons | `ribbon`, `ribbon_fast`, `ribbon_twist`, `ribbon_double`, `ribbon_cage` |
| Curtains | `wave_A`, `waves_AB` |
| Ocean | `ocean`, `ocean_swell`, `ocean_storm` |
| Planes | `plane_flat`, `plane_sweep`, `plane_tilt`, `fw_static`, `fw_scan`, `fw_stack`, `fw_breathe`, `fw_rock`, `fw_ripple`, `fw_split`, `fw_rain`, `fw_ribbon` |
| Warp-corrected planes | `fwc_static`, `fwc_scan`, `fwc_stack`, `fwc_rock`, `fwc_ripple`, `fwc_split` |
| Solids | `ball_bounce`, `ball_pulse`, `tower_twist`, `layer_scan`, `orbit`, `sphere_round`, `sphere_pulse`, `sphere_bounce` |

**Other commands:**
- **Demo:** `.\tools\demo_planes.ps1`
- **Calibrate:**
  - `python -m vol2.calib_sweep capture --map configs/case_map_tank_v2.json`, then `analyse <run>`. The automatic fit can fail; the fixed-corner refit is `calib_sweep.fit_columns(left, corner, right, D)`.
  - `python -m vol2.calib_duty duty` (writes `duty_roi.json`; `analyse <run>` re-derives it offline)
  - `python -m vol2.warp_scan capture`
  - `python -m vol2.warp_test <warp_run>`
- **1440 Hz sub-frames** (needs Joey's GUI mode switch; **not yet run**):
  - `python -m vol2.subframe build <scene>`: each build folder gets a `procedure.txt`.
  - `python -m vol2.subframe planecheck`, then `python -m vol2.subframe play vol2\out\subframe\plane_check`.
  - Do not use `tools/play_loop.py` for packed frames: it reads grayscale.
- **Holding frames:** `python tools/play_loop.py <s/frame> <loops> <png…>` with `PLAY_COLOR=blue` holds **mono 0/255** frames only (e.g. `*_hdmi.png`). For BGR or graded frames use `volplay` or `tools/shoot_bgr.py`. `holo/holo_show.py` holds a mono frame and takes a camera snapshot.

**Code map:**

| Area | Files |
|---|---|
| Geometry, rays, rendering | `vol2/geometry.py`, `render.py`, `simulate.py` |
| Shapes and animation | `rods.py`, `anim.py`, `solid.py`, `solid_bonly.py`, `oneface.py` |
| Player, sub-frames, pattern packs | `volplay.py`, `subframe.py`, `flashpack.py` |
| Calibration | `calib_sweep.py`, `calib_duty.py`, `warp_scan.py`, `warp_test.py`, `edge_quality.py`, `plane_color.py`, `plane_geom.py` |
| Rig access (the only hardware layer) | `rig/config.py`, `lock.py`, `safety.py`, `hdmi.py`, `camera.py`, `bench.py` |
| Bench tools | `tools/shoot_set.py`, `shoot_bgr.py`, `numgrid.py`, `play_loop.py`, `make_gif*.py`, `demo_planes.ps1` |
| Holography | `holo/` |

---

## 6. Figures

All camera images are background-subtracted (black frame), cropped, and display-stretched (percentile scaling, gamma 0.6). **GIFs are stop-motion:** 16 frames each held and photographed one at a time, not real-time video. The source run names are kept for the record; raw runs are not in the repo.

| File | What it shows | Source |
|---|---|---|
| 01_sep29_empty_case_cube_on_wall | Wireframe / tube / solid cube on the empty case: lands on the wall and the back face | 20260929T115303_cube |
| 02_hologram_sim_cube_focus_stack | Simulation. Rows = refocus planes 0.38 / 0.40 / 0.42 m; left = simulated intensity, right = layer target | holo/out |
| 03_hologram_sim_led_coherence | Simulation. Columns: laser, LED 30 / 10 / 3 nm @ 75 µm pinhole, 10 nm @ 200 µm, 500 µm, bare die; rows = the three planes | holo/out |
| 04_flood_both_faces_glycerin | Face A flood, face B flood, both | 20261005T073610_flood_v2 |
| 05_column_sheets_curved_edge_scan | One column at a time (number = DMD col) | 20261005T073636_calib_blue |
| 06_first_helix_and_cube | Helix, 18 mm cube, 13 mm cube at 45°, cube from plane A only | 20261005T074629_v2_content |
| 07_string_art_box_pyramid_diamond | Rod layers; bottom row: dense walls, helix, cube | 20261005T080101_rods_v3 |
| 08_13layer_stills_… | 13-layer stills | 20261005T080706_anim_stills |
| 09 / 10 GIFs | Twisting tower / breathing diamond, stop-motion | 20261005T0807xx_anim_* |
| 11 / 12 | Simulated orthographic views from 4 azimuths / several elevations | vol2/out/anim_glycerin_v3 |
| 13_B_input_A_output | Top: B flood, B sheets, B rows. Bottom: B-only rod shapes (labels say "B_") | 20261005T082044_B_in_A_out |
| 14_one_face_direct_x_reflected | Shapes from face-B mirrors only (direct × reflected) | 20261005T082437_oneface_B |
| 15_floating_shapes_off_corner | Off-corner shapes at qa = qb = 40 mm | 20261005T083537_float2_stills |
| 16_solid_shapes_two_faces | Solids, 67 ms (top) / 200 ms (bottom) | 20261005T083931_solids |
| 17_solid_shapes_B_only | Top "bband" = B band only; bottom "brefl" = direct × reflected | 20261005T084430_solids_bonly |
| 18 / 19 | Plane colour test images / profile along the plane band | 20261005T100214_plane_color |
| 20_plane_geometry_test | 15 plane geometries with coverage, evenness and glow ratio printed under each | 20261005T100412_plane_geom |
| 21_distortion_grid | Camera positions of scanned mirrors: yellow = along DMD rows, blue = along DMD columns, white = dots | 20261005T100830_warp_scan |
| 22_plane_before_after_warp_correction | Top: uncorrected; bottom: corrected; red line = target level | 20261005T101906_warp_test |
| 23_* GIFs | Plane animations, stop-motion (fwc_ = warp-corrected) | 20261005T102150_plane_anims |
| 24_two_family_coverage_plan_sim | Model plan view, mid-height: blue = A only, orange = B only, white = both | vol2/out/glycerin_tir_v3 |

---

## 7. Open questions and next steps

1. **Validate the calibration on held-out data:** predict the warp-scan dots or the row-sweep edges from `case_fit_tank_v4` and report the error. Measure projector pitch and D.
2. **Measure the absorption length** L (the player assumes 30 mm).
3. **Extend the warp correction** to the outer edges (a denser scan near cols 560–610 and 750–785). Mark dots that fall outside the case outline.
4. **Model the inverted case:** clear acrylic floor, black base overhead.
5. **Log playback** for the fw_* / fwc_* scenes, and verify DMD-side frame timing (photodiode or high-speed camera).
6. **Stereo capture** (two camera positions) to document the 3D form the single camera cannot show. Capture the ribbon-only scenes, which have no images yet.
7. **Run the 1440 Hz video-port pattern mode** (Joey's GUI step) and compare with 60 Hz.
8. **Round cross-sections:** face A's light reflected off the bare back wall is ~perpendicular to face B (panel model), at the cost of extra crossings.
9. **True voxels:** a moving screen (Geng-style helix) in air, or a two-step dye.
10. **Coherent holography:** LED + pinhole + collimator onto the bare DMD, if Joey wants the build. Designs are in `holo/`; the light-vs-depth trade is in `holo/coherent_build.py` (`data/results/hologram_coherent_build.json`, simulation and arithmetic only).

---

## 8. Where things are in this repo
- `docs/figures/`: 23 numbered figures (01–22, 24) plus 8 plane-animation GIFs numbered 23 (5 fwc_, 3 fw_). See §6.
- `data/calibration/`: the duty curve and warp map the player falls back to.
- `data/results/`: measured results (warp test, plane colour and geometry, calibration sweep, edge quality, playback stats) and simulation reports (hologram, two-family model, animations, rotation / corner-gap sweep).
- `configs/`: bench records, case maps and fits.
- `docs/LAB_LOG.md`, `docs/RESULTS_2026-09-29.md`: the running log and the first day's results.
- Code: see the code map in §5 and the README.
