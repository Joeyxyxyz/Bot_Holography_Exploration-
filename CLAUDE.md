# CLAUDE.md: rules for AI coding sessions in this repo

Read `README.md`, `SAFETY.md` and `docs/BRIEFING.md` before changing anything. `BACKLOG.md` lists the work.

## 1. You are not at the bench

- **Never run anything that opens the DMD window, the camera or the rig lock.** That includes:
  - `vol2.volplay` without `--dry`;
  - `vol2.calib_* capture` / `duty` / `rate`, `vol2.warp_scan capture`, `vol2.warp_test`, `vol2.plane_*`, `vol2.oneface_edges`, `vol2.twoface_map`;
  - `vol2.subframe play`;
  - `tools/play_loop.py`, `tools/shoot_*.py`, `tools/demo_planes.ps1`;
  - `holo/holo_show.py`;
  - `python -m studio` (Holo Studio) unless `DLP_NO_HARDWARE=1` is set. With it set, the studio is preview-only and you may run it to check the page.
  - Never use a Holo Studio you did not start yourself with `DLP_NO_HARDWARE=1`: one already running on this machine may be live. That means not pressing Play, Play all or Show grid on it, and not calling `/api/play`, `/api/playlist`, `/api/grid` or `/api/stop`.
- Set `DLP_NO_HARDWARE=1` in your shell. The tests and CI set it already.
- If a change needs a bench check, write the exact command for Joey under a **"Bench check (Joey)"** heading in the PR description. Don't run it yourself.
- **Physical steps, projector GUI, firmware and flash, and LED currents are Joey's.** Code never sends USB/HID to the projector and never changes LED currents.

## 2. Machine safety is not negotiable

- `rig/` is the only hardware layer. Don't add hardware access anywhere else.
- Scripts use `with rig.bench.Bench(...)`, or `lock, sync = open_rig()` with `sync.close(); lock.release()` in a `finally`.
- Never import USB/HID packages (`hid`, `usb`, `pycrafter4500`, …) or write LED, mode or source command code.
- Never weaken or skip a guard or a safety test (`tests/test_static_safety.py`, `tests/test_rig_safety.py`) to make something pass. Changes to `rig/` or those tests need Joey's review: say so in the PR.
- Frames are exactly 1140 × 912 `uint8` (mono or BGR) and are shown 1:1. Never scale on the way to the DMD.

## 3. Say only what was shown

- Tag claims: **[PROVED]** (measured, or arithmetic or simulation stated as such), **[ASSERTED]** (standard physics or vendor data) and **[HEURISTIC]** (judgement, a visual read, or a placeholder).
- Simulation results are simulation. Offline work can't confirm anything about the physical case.
- This is volumetric projection, not holography. A camera image of a pattern is never a "holographic reconstruction".
- One camera can't show 3D form. Don't claim 3D from a single view.
- Don't change the recorded results in `data/` or `docs/`. Add new results next to them, with their date and source.

## 4. Public-repo hygiene

- No company, employer, station or customer names. No personal paths (`C:\Users\…`), emails or machine names.
- No large binaries. Captures go to `runs/`, which is git-ignored.

## 5. Working style

- Small, focused branches and PRs. `python -m pytest` must pass. Add tests for new scenes and models.
- Keep the existing style: compact numpy, short comments that give the reason, and tags in docstrings.
- The bundled calibration (`data/calibration/`) is one bench day (2026-10-05). It is not a general model of the case. If the case moves, the column windows in `vol2/volplay.py` and the case fit in `configs/` must be re-measured on the bench.
