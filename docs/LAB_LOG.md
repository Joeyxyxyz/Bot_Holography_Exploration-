# Volumetric projection into the case — status and next steps (2026-09-29, revised after review)

Tags: [PROVED] = measured here, or arithmetic/simulation stated as such; [ASSERTED] = standard physics or vendor data;
[HEURISTIC] = judgement or placeholder model. No holographic reconstruction has been measured on hardware.
The adversarial review (9 agents, `vol2` model + docs) and what was done about it is at the end.

## A. Two-plane projection with the stock projector (current path)

**Setup (Joey, grid call-outs 12:25–12:39, `case_map_tank_v1.json`):**
- The case is corner-on. Plane A = face toward the camera, DMD cols ~544–628 (dots confirmed at 550–620).
- The rounded edge is col-8 band 628–656, kept dark. Plane B = face toward the projector side, cols 656–740 (dots at 662–736).
- Acrylic rows are ~624/673–1016 and the black base is 1016–1065. These are 28-column grid-cell boundaries, not sub-mirror edges.
- The case was taken off to drain after the water test, so all placement must be re-checked when it is back (§A.5).

**A.1 Two ray families.**
- Each face refracts its part of the beam toward its own normal, so two ray families cross inside the liquid.
- Collimated-beam crossing angle: 25.9° water / 32.5° glycerin corner-on [PROVED, Snell, collimated limit].
- The projector's fan raises the incidence on both faces, so the traced model gives 22.3° (water) / 29.3° (glycerin) at the plane median, and about 19–25° by column pair [HEURISTIC model, `vol2/check_model.py`].
- Read angles off a photo only with a known camera pose.

**A.2 Where both families reach.**
- Both families drift away from the corner, so their overlap is a wedge opening at the crossing angle toward the back corner.
- Largest jointly reachable plan square, checked at 13 heights with the walls sampled exactly: 13.9 mm (water) and 18.4 mm (glycerin) [HEURISTIC model]. This is with the entry cut 8 mm from the corner (the dark col-8 band). A ~3–4 mm cut (the real rounding) enlarges it (`vol2/sweep_psi_gap.json`).
- Rotating the case ±10° barely changes it.

**A.2b What content can be clean: one point per height** [PROVED, geometry + `vol2` simulation].
- Both families lie in near-horizontal fans. A horizontal line therefore lights a whole plane: its A rays and its B rays form the same horizontal sheet.
- n points at the same height light n² crossings, n real and n² − n ghosts of equal brightness.
- In a linear medium (scattering, ordinary fluorescence) time-multiplexing does not help: eye and camera add light over time just as the medium adds it in space.
- **Ghost-free content = curves with one point per height**: a helix, a slanted line, a single vertical line.
- Simulated (glycerin, 1 mm beams, target peak / far-beam level):

  | Content | Result |
  |---|---|
  | Helix (130 points, r = 7.7 mm, pitch 20 mm) | **2.75**, crossings 0.32 mm from the curve (median) |
  | 18 mm cube | 2.37, but its top and bottom squares light whole slabs and its vertical edges bring 12 ghosts per height |
  | Plane A only | 1.42 |

  Views: `vol2/out/glycerin_absorb/*_views.png`. Crossings-only renders are in the same folder: `helix_crossings_only.png`, `cube_for_ghosts_crossings_only.png`.
- A true floating cube (every edge, no ghosts) needs a nonlinear medium that glows only where two beams overlap, such as a two-step photoactivatable dye.

**A.3 Total internal reflection (review, confirmed and reproduced).**
- In water, 67% of every family's direct beams hit a side wall or the surface beyond the critical angle.
- At the back walls (55–57°, n·sin = 1.09–1.12) the light enters the acrylic, is totally reflected at the outer acrylic/air face, and returns walked off ~3.3 mm. Glycerin: 57%.
- These ghost legs add ~20% light in the target zone and extra crossings.
- **Physical fix:** black vinyl tape, or matte black paint, in full contact with the OUTSIDE of the two back walls. The adhesive or binder (n ~1.5 > 1.12) frustrates the reflection and absorbs the light; it also darkens the background.
- The model has both options: `Case(back_walls="tir")` for bare acrylic, `"absorb"` for taped. Taped: 93% of direct beams are absorbed at the back walls [HEURISTIC model].
- The target / far-beam ratio barely changes with the tape (18 mm cube 2.44 bare vs 2.37 taped, glycerin). The tape is **optional**: it removes ghost legs and glare, not contrast.

**A.4 Beam width.**
- Each mirror is modelled as its chief ray. Through the stock F/2.1 lens a mirror's beam is ~0.5–1.8 mm wide at the case, depending on focus (review).
- **Focus the stock lens onto the middle of the case before any volume run.** It is probably focused at the wall now.
- A crossing of two beams of width w is elongated along the bisector by ~w / sin(θ/2): ~5 w in water.

**A.5 Calibration first (review, confirmed).**
- The column scale was fitted to grid-cell edges (cpm 2.49 is the UPPER cell-boundary fit; the call-outs allow ~1.8–2.49).
- The shallow crossing magnifies a lateral error ~5×, so placement is uncertain by several mm up to ~12 mm inside a 14 mm zone until calibrated.
- The LightCrafter's 100 % throw offset means the corner ray is not necessarily horizontal (pitch unknown).
- `vol2/calib_sweep.py`, once the case is back with the fluorescent fill:
  - `capture` sweeps single 2-mirror columns across both faces and single rows in each plane, in blue.
  - `analyse` finds the half-maximum edges of the in-liquid glow and fits col_corner / cpm / psi. On a synthetic pose it recovers (638, 2.40, 3°) with zero residual [PROVED, offline].
  - Pitch and base row come from the row sweeps.

**A.6 Measured so far.**
- Clear water, 13:08–13:15 (`runs/20260929T130848_water_twoplane`, `..._clearwater_scatter`): the dots, sheets and cubes land on the back walls. Nothing is visible inside the water, even with every mirror on at 0.2–0.5 s exposure [PROVED]. Clear water and clear glycerin do not scatter.
- The 13:20 beam test (`runs/20260929T132006_cones`) ran after the case had been removed. It shows the wall only.

**A.6b Measured 2026-10-05: glycerin + highlighter, case upside down, projector moved back** [PROVED unless tagged].
- Map: Joey's call-outs, `case_map_tank_v2.json`. Plane A = cols 7–10 (DMD 544–656), corner = col 11 (656–684), plane B = cols 12–14 (684–768).
- Blue flood (`runs/20261005T073610_flood_v2`): the whole liquid fluoresces from either face.
- Calibration sweep (`runs/20261005T073636_calib_blue`): each column is a glowing sheet in the liquid. Silhouettes at cols 583.4 / 764.2.
- Fit with the corner fixed at Joey's col 11 (670): cpm 2.36, psi +2°, residual 0.45 col (`case_fit_tank_v2.json`; D 430–530 fit equally).
- Rows: the liquid spans ~850–1095 [HEURISTIC, row-sweep edges].
- The automatic corner pick failed (profile dips at ~642 / ~696). The rounded edges modulate the profile; this edge model needs work.
- Content built for this geometry (`vol2/out/glycerin_tir_v2`) and photographed (`runs/20261005T074629_v2_content/montage.png`):
  - **Helix:** two bright zigzags (each family's lit edge), faint structure between them.
  - **Cubes:** a box outline with vertical bars.
  - **Plane-A-only cube:** looks nearly the same as the two-plane cube from this one camera.
  - So a single view does not show the 3D crossing yet. Judging depth needs a second viewpoint (eye or camera moved), as predicted in A.2b.
- Joey: the four rounded vertical edges can warp the light. Planned: exclusion bands at the silhouettes as well as the front corner, then a measured warp from a two-view sweep.

**A.6c Curved-edge scan and "string art", 2026-10-05.**
- Per-column sheet contact sheet (`runs/20261005T073636_calib_blue/sheets_contact.png`):
  - Plane A cols 582–654 give one clean straight sheet each.
  - Cols ~660–678 smear (the rounded corner is wider than col 11).
  - Plane B cols ~684–750 are seen by the camera through the curved vertical edge (a viewing warp, not only a projection warp).
  - Content is now built from the clean columns only: `case_fit_tank_v3.json`, A 584–654, B 684–750.
- `vol2/rods.py`: shapes made of rods (1 plane-A or plane-B mirror block = 1 glowing rod at one height). Each layer = 2 A + 2 B rods, whose 4 crossings are its corners, with no ghosts at that height.
- Photographed (`runs/20261005T080101_rods_v3/montage.png`): the pyramid (5 layers) and diamond (7 layers) outlines read clearly from the camera, as layers of bright points narrowing / widening. A 3-layer box shows as 3 rows of point pairs. Dense layers ("walls") show as vertical glowing sheets. [PROVED, camera]
- This is currently the most recognisable 3D content. The rods still run wall to wall; the shape lives in their crossings and end points.

**A.6d More layers and motion, 2026-10-05 (Joey: no extra dye; more layers, active projection).**
- `vol2/anim.py`: 13 layers, 3.25 mm apart, through the ~49 mm of glycerin. Frames up to 13.1 mm (0.8 × the joint box).
- Stills: sphere, hourglass, cage, pyramid, inverted cone. All read clearly on camera (`runs/20261005T080706_anim_stills/montage.png`) [PROVED, camera].
- Animations (16 frames each, HDMI playback via `play_loop.py 0.1 …` at ~10 fps; `play_loop` now drops the 0.35 s hold floor for short frames):
  - breathing diamond;
  - rising wave;
  - twisting tower (frame centres orbit 2.9 mm with a height-dependent phase);
  - morph (box → pyramid → diamond);
  - bounce.
- Camera recordings, frame by frame: `runs/20261005T080721_anim_tower/camera_animation.gif`, `runs/20261005T080747_anim_diamond/camera_animation.gif`.
- Each animation also has a 16-slot pattern-mode pack (`flash_pack/`, 40 ms slots, blue) for the GUI, files only.

**A.6e Input B / output A, one-face reflections, floating and solid shapes, 2026-10-05.**
- The earlier "shapes" on camera were largely the entry pattern on face A, which the camera looks through. Joey's input / output split:
  - B-only light seen through face A (`runs/20261005T082044_B_in_A_out`): the volume glows, with no entry picture.
  - One-face two-family mode (`vol2/oneface.py`): direct × totally reflected B rays, model crossing 58°. Dim on camera.
- Joey: the beams fade about the centre (fluorescein absorption).
- Floating content was moved to the centre region. A wider corner keep-out was needed (Joey saw corner bending): `case_fit_tank_v4.json` uses A ≤ 645, B ≥ 695, r_corner 12 mm.
  - Clean overlap starts ~35 mm from the corner on each face; objects are placed at qa = qb = 40 mm.
  - Joey: "it's not hitting" the corner now.
- **Solid shapes** (`vol2/solid.py`): each 1 mm layer = a filled band of A rays × a filled band of B rays → one glowing rhombic cross-section at 2×, no ghosts.
  - Cube, ball, pyramid, diamond and inverted cone (7 mm × 14 mm) read clearly as solid silhouettes on camera (`runs/20261005T083931_solids/montage.png`) [PROVED, camera].
  - Animations: bouncing ball, pulsing diamond.

**A.6f Refresh and duty: the volume player, 2026-10-05.**
- **Duty curve** (`vol2/calib_duty.py duty`, ROI-based, `runs/*_duty/duty_roi.json`), blue level → relative glow:

  | Level | 0–48 | 64 | 96 | 128 | 160 | 192 | 224 | 255 |
  |---|---|---|---|---|---|---|---|---|
  | Glow | ~0 | 0.03 | 0.10 | 0.22 | 0.44 | 0.66 | 0.87 | 1.0 |

  A dead zone, then roughly a 2.6 power. The player uses the measured table, not a gamma [PROVED, camera].
- **Refresh:** the HDMI window accepts ~225 pushes/s, so the DMD's 60 Hz is the limit. `vol2/volplay.py` plays pre-rendered clips on a fixed 60 Hz clock: **achieved 60.0 fps, 0 dropped** (waves_AB, 15 s) [PROVED].
- **Duty per element** (rod / band / curtain row) uses the measured table, with exp(depth / L) absorption compensation (L = 30 mm [HEURISTIC]).
- **Scenes:**
  - solids (pose-fit dependent): ball_bounce, ball_pulse (duty breathing), tower_twist, layer_scan, orbit;
  - curtains designed in DMD space (pose independent): wave_A, waves_AB, ribbon.
- **Faster than HDMI (GUI, Joey):** DLPU011E Table 4-1 gives 1-bit patterns streamed from the video port at up to 2880 Hz, and 4225 Hz preloaded. With VSYNC trigger, each 60 Hz frame's 24 bit-planes play as 24 sub-frames (1440 Hz, Geng 2013 "bit-plane splitting"). In that mode duty = sub-frames on / 24, a linear 25-step scale. Not yet used.
- In a linear medium, fast sub-frames add up like space does: speed buys smoothness and duty control, not depth gating. Depth gating needs a moving screen (Geng's helix) or a two-step medium.

**A.6g Stronger flat plane, corner bending, distortion scan and correction, 2026-10-05.**
- **Colour vs penetration** (`vol2/plane_color.py`, `runs/20261005T100214_plane_color`):
  - Blue gives the cleanest fluorescent plane.
  - Green and white add real in-liquid glow (baseline ~2–3× blue) but also bright glints at the acrylic edges.
  - Red shows only as reflections.
  - Best balance: blue core with green edging; pure blue for the cleanest look [PROVED, camera].
- **Plane geometry** (`vol2/plane_geom.py`, `runs/20261005T100412_plane_geom`):
  - **Full width, corner INCLUDED, blue**: the rounded corner spreads its light and fills the gap between the faces. One continuous plane, 2.1× the glow of the clean windows.
  - **12 rows thick**: 4.3× the glow at the same evenness.
  - A 40-row slab is a bright layer (15×).
  - The corner alone makes a short fan; the outer edges alone make almost nothing.
- **Distortion scan** (`vol2/warp_scan.py`, `runs/20261005T100830_warp_scan/warp_grid.png`): a single dot at a time on a 23 × 12 grid, 177 found.
  - Straight DMD rows come out tilted (slope ~0.1) and bowed (RMS ~6 px, max ~11 px).
  - Face B (the direct path) is the most regular.
  - Face A's far outer edge throws its dots far to the left; face B's outer edge throws them back toward the middle.
  - Matches Joey's description (A bends lines right; the far A corner bends hardest).
- **Correction** (`vol2/warp_test.py`, `runs/20261005T101906_warp_test/before_after.png`): rows chosen per column from the map, over cols 610–750.

  | Plane | Slope | RMS | p95 |
  |---|---|---|---|
  | Uncorrected | 0.026 | 3.0 px | 5.4 px |
  | Corrected | 0.003 | 1.2 px | 2.9 px |

  The correction straightens what the camera sees; it is viewer-dependent [PROVED, camera].
- **Animations** (`vol2/volplay.py`):
  - corrected: fwc_static, fwc_scan, fwc_stack, fwc_rock, fwc_ripple, fwc_split;
  - plain: fw_static, fw_scan, fw_stack, fw_breathe, fw_rock, fw_ripple, fw_split, fw_rain, fw_ribbon.
  - Camera GIFs: `runs/20261005T102150_plane_anims/*.gif`. One-command demo: `demo_planes.ps1`.
- **Open:**
  - the corrected planes curl up at the outer edges, outside the scanned smooth region;
  - a denser scan (step 5 columns) and the outer edges would extend it.

**A.7 Fill.**
- Glycerin + 2–3 drops of yellow-highlighter extract (fluorescein / pyranine): a faint tint, not dark.
- Optionally 1 drop of whole milk. Stir slowly and let the bubbles clear.
- Project in blue: `set PLAY_COLOR=blue` for `play_loop.py`; `calib_sweep` uses blue by default. Blue lights only the blue LED sub-frames over HDMI; LED currents are unchanged.

**A.8 Session order when the case is back:**
1. Case in the same spot, corner to the projector. Tape on the back walls if possible. Lens focused on the case.
2. Lights off.
3. `python numgrid.py` + hold: quick placement check.
4. `python -m vol2.calib_sweep capture`, then `analyse`. Refit Case, then `python -m vol2.run --fill glycerin`.
5. `play_loop.py` / `shoot_set.py` with the rebuilt frames. **Helix first** (`vol2/out/glycerin_absorb/helix_hdmi.png`, then `anim_helix_rotate/`). Compare with `vol2/out/*_views.png`.

**Pattern mode.**
- `vol2/flashpack.py` writes a 16-slot (G0–G7, R0–R7) one-image pack, so a GUI G/R swap is only a rotation. The built pack is a rotating helix: `vol2/out/glycerin_absorb/flash_helix_rotate/`, 16 × 20 ms, blue LED. It also writes a plane-check image (slot k shows digit k) and `procedure.txt` following FLASH_FASTSCAN_4500.md §5 step by step.
- Files only: every GUI step is Joey's, after a firmware backup. Nothing has been run in pattern mode.

## B. Holography (coherent) — parked by Joey's choice (no pinhole)

- **Coherence, not a laser, is the requirement.** An LED works if it is spatially filtered.
- Simulation (`holo/led_study.py`, correlation of each refocused plane with each layer target; laser diagonal 0.265 / 0.476 / 0.190) [PROVED, this simulation only]:

  | Illumination | Near / middle layers | Far layer |
  |---|---|---|
  | Laser | separated | separated |
  | LED + 75 µm pinhole | separated | **not separated** (0.109 / 0.118 / 0.117 at 30 nm) |
  | LED + 200 µm pinhole | **no depth separation**: every plane correlates best with the near target | — |
  | LED + 500 µm or bare die | washed out | washed out |

  Bandwidth (30 / 10 / 3 nm) matters little next to the pinhole. The earlier "less speckle than the laser" was not measured and is withdrawn.
- **No holographic depth through the stock lens.** The lens magnifies the DMD by M ≈ 37–40× at the case: 0.40–0.43 mm per column against the 10.8 µm column pitch, from the cpm fit, not a separate measurement [HEURISTIC]. Diffraction angles shrink by M and depth resolution grows by ~M², to roughly 0.6–0.7 m [HEURISTIC scaling]. Holographic depth in a 60 mm case needs the DMD lit by a collimated, pinhole-filtered source with no magnifying lens.
- **Lensless cube design** (`holo/fresnel_cube.py`, 532 nm, layers 0.38 / 0.40 / 0.42 m):
  - The focus stack separates the front and back faces in simulation.
  - Lattice-model mismatch (diamond vs rect) costs ~10 % correlation.
  - Amplitude clipping to the 90th percentile gives 5× light at equal fidelity [PROVED, this simulation].
- **T2 sweep** reproduces 0.977 at f_c = fill = 0.125 and fails for fill > 1.33 f_c. T3 budget and T4 lattice discriminator are in `holo/out/prep_report.json`. T4 needs coherent light on the bare DMD and cannot run through the stock lens.

## C. Lean inputs read today
- `output88_cube_projection`:
  - constants and counts only, no cube geometry;
  - its depth strategies (PWM duty, frequency→depth, parallax) are not physical depth mechanisms;
  - "p²/λ ≈ 108 mm Fraunhofer" is off by 1000×.
- `output92_signed_depth_multiplexing`:
  - signed carriers / ON-OFF groups as ±depth conflict with correction #2 and with Babinet;
  - the original likely does not compile (read only).
- `MNF Kinetic & Thermal Ledger.html`: not DMD-related.

## D. Review log (2026-09-29, 4 reviewers + 5 adversarial verifiers; all 5 verified findings upheld)

| Finding | Status |
|---|---|
| TIR at the back walls unmodelled | **fixed** in `vol2/geometry.py` (legs, walk-off, `back_walls`); tape recommended |
| Scale / pose from cell-quantised call-outs; throw-offset pitch | model generalised (c0 / r0 / pitch); **calibration step added**; placement not trusted until fitted |
| Crossing angle quoted as the collimated value | restated (A.1); `dual_face.py` prints both |
| LED table overstated | restated (B) |
| 24-slot flash pack not a pure rotation under a G/R swap; procedure missing safety steps | fixed: 16 slots, plane check, `procedure.txt` |
| joint_box over-claimed, anchored at the back corner | fixed: DP over all squares, conservative side |
| Rod blocks off-centre; A / B picked independently | fixed: odd centred blocks, joint pair choice with crossing error reported |
| Chief-ray model ignores beam width; contrast metric aliased | beam blur and far-beam contrast in `simulate.py`; lens focus added to the session |
| `dual_face --split` ignored; STOP race; holo_show wording | fixed |
| Stale footprint in RESULTS | correction note added |
| Diamond half-column row offset not in `pixel_dirs` | **open**: parity unknown; the calibration sweep will show it |
