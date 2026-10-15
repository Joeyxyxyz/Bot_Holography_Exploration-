# Machine safety

This code drives a real projector and camera on a bench with a liquid-filled case. Machine safety comes first. Most rules below are **enforced in code and checked by the tests**; the rest are for people.

## The bench

- **Projector:** TI DLP LightCrafter 4500 (EKB "4500 MKII" build, DLPC350 controller). Stock LEDs and lens. Driven only as an HDMI monitor: 912 × 1140, video mode, at desktop position (1920, 0) by default (`DLP_MONITOR_OFFSET`).
- **Camera:** FLIR Blackfly S (mono) through PySpin.
- **Case:** a small acrylic case of glycerin with fluorescein dye, in front of the lens.
- **Other programs:** another program on the same PC (the swiss-army-scanner) drives the same projector and camera. The two share one machine-wide **rig lock**.
- **Desktop:** give the DMD display a plain black desktop background with no icons or windows. When a program closes its window, the DMD shows that desktop.

## Rules the code enforces

| Rule | How it is enforced | Checked by |
|---|---|---|
| **One program on the rig at a time.** The lock is taken before the camera opens or the window paints. If it is held, stop: never break it, delete it, or kill its holder. | `rig/lock.py` holds an OS byte lock on byte 0 of `%PROGRAMDATA%\swiss_army_scanner\rig.lock`, the same file and mechanism as the scanner. The path is deliberately not configurable. A busy lock raises `RigBusy` with the holder's name. If the holder dies, the OS frees the lock, so there is never a stale lock to break. | `tests/test_rig_safety.py` (exclusion, the scanner's path, byte-0 lock) |
| **HDMI video mode only.** Never send DLPC350 USB/HID commands (mode, source or LED changes). | `rig/` has no USB/HID code. `rig.safety.check_no_usb_hid()` refuses to open the rig, and to show **any** frame, while a USB/HID module (`hid`, `usb`, `usb1`, `pycrafter4500`, …) is loaded in the process. | `test_static_safety.py`: no USB/HID imports and no DLPC350 command ids (16-bit or split-byte) anywhere. `test_rig_safety.py` |
| **Code never changes LED currents.** | There is no LED code. Colour comes only from the HDMI frame: a blue-only frame lights only the blue LED's sub-frames. | `test_static_safety.py` (no LED-current names or command ids) |
| **Frames are shown 1:1 on the mirrors.** | `rig.safety.check_frame()` accepts only an exact 1140 × 912 frame (mono or BGR) of `uint8`; anything else is refused before it reaches the window. When the window opens, it paints black and checks its own position and size. If it is not exactly the DMD display (wrong monitor, display scaling), it closes and refuses, so nothing is projected scaled. | `test_rig_safety.py` |
| **Hardware only through `rig/`.** | Outside `rig/` there is no PySpin, no OpenCV display window, no direct `HDMIWindow`, `Camera` or `RigLock`, and no process launch, `ctypes` or dynamic import. Scripts use `with rig.bench.Bench(...)`, or the `open_rig()` pair with `sync.close()` and `lock.release()` in a `finally`. | `test_static_safety.py` |
| **Leave the bench dark and free on every exit.** | `Bench.close()` runs these steps in order: show black for at least two HDMI frames, close the window, close the camera, release the lock. They are nested `finally` blocks, so each step runs even if an earlier one fails, on errors, on Ctrl+C and after a failed camera open. Calling it twice is safe. | `test_rig_safety.py` |
| **No hardware from tests, CI or cloud sessions.** | `DLP_NO_HARDWARE=1` makes `Bench`, `HDMIWindow` and `Camera` refuse before touching the lock. The tests and CI set it. Tests that switch it off replace every device with a fake. | `test_rig_safety.py` |

**Tools that only write files.** `vol2/flashpack.py` and `vol2.subframe build` / `planecheck` write images and a step list (`procedure.txt`), and send nothing to the projector. `vol2.subframe play`, `vol2.volplay` (without `--dry`), `holo/holo_show.py` and the capture scripts do project. They go through `rig.bench` like everything else.

The static checks are a tripwire for ordinary code, not a sandbox: deliberately obfuscated code could get past them. That is why changes to `rig/` and to these tests need review (below).

## Rules for people

- **Physical steps are Joey's:** moving or filling the case, aiming or focusing, cabling, the camera lens, and power.
- **Firmware, pattern or flash modes, and LED currents are set only by Joey,** in the EKB 4500 MKII GUI, after a firmware backup. The `procedure.txt` files are step lists for those GUI steps.
- **Don't hold the rig longer than a capture session.** Players stop at their time limit or when a `STOP` file appears in the repo root. Hold durations are command-line arguments; keep them short.
- **Check the case didn't move before trusting a calibration.** Generate the numbered grid (`tools/numgrid.py`) and hold it (`tools/play_loop.py` or `holo/holo_show.py`), or re-run the column sweep, before playing warp-corrected scenes.
- **Eyes:** don't look into the projector lens. The blue LED is bright at close range.
- **Liquids:** keep the glycerin case and any spills away from the projector and the camera electronics.

## Stopping

- **A running player or hold:** create an empty file named `STOP` in the repo root, or press Ctrl+C in its terminal. The DMD goes dark, then shows the desktop, and the lock is released.
  - PowerShell: `New-Item STOP`
  - cmd: `type nul > STOP`
  - bash: `touch STOP`
- **The demo playlist** (`tools/demo_planes.ps1`): create `STOPALL` first, then `STOP`. `STOP` alone ends only the current scene, and the next scene would start.
- **The capture scripts** (calibration, scans) don't watch `STOP`. They are short. Press Ctrl+C to end one early.
- **If a process hangs:** close its window or end the process. The OS releases the lock when the process ends.
- **Never** delete `rig.lock` or kill another program's process to get the rig.

## Changing `rig/`

`rig/` is the only layer that touches hardware. Changes to it, or to `tests/test_static_safety.py` and `tests/test_rig_safety.py`, need Joey's review. Never weaken a guard to make something work. If a guard blocks you, stop and ask.
