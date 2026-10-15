# Machine safety

This code drives a real projector and camera on a bench with a liquid-filled case. Machine safety comes first. Most rules below are **enforced in code and checked by the tests**. The rest are for people only.

## The bench

- **Projector:** TI DLP LightCrafter 4500 (EKB "4500 MKII" build, DLPC350 controller). Stock LEDs and lens. Driven only as an HDMI monitor: 912 × 1140, video mode, at desktop position (1920, 0) by default.
- **Camera:** FLIR Blackfly S (mono) through PySpin.
- **Case:** a small acrylic case of glycerin with fluorescein dye, placed in front of the lens.
- **Other programs:** another program on the same PC (the swiss-army-scanner) drives the same projector and camera. The two share one machine-wide **rig lock**.

## Rules the code enforces

| Rule | How it is enforced | Checked by |
|---|---|---|
| **One program on the rig at a time.** Take the lock before opening the camera or painting the DMD window. If it is held, stop: never break it, delete it, or kill its holder. | `rig/lock.py`: an OS byte lock on `%PROGRAMDATA%\swiss_army_scanner\rig.lock`, the same file and mechanism as the scanner. A busy lock raises `RigBusy` naming the holder. The OS frees it if the holder dies, so there is never a stale lock to break. | `tests/test_rig_safety.py` |
| **HDMI video mode only.** Never send DLPC350 USB/HID commands (mode, source or LED changes). | `rig/` contains no USB/HID code. `rig.safety.check_no_usb_hid()` refuses to open the rig, or to project a frame, if a USB/HID module is loaded in the process. | `test_static_safety.py` (no `hid` / `usb` / `pycrafter4500` imports, no DLPC350 command ids anywhere); `test_rig_safety.py` |
| **Code never changes LED currents.** | There is no LED code. Colour comes only from the HDMI frame: a blue-only frame lights only the blue LED's sub-frames. | `test_static_safety.py` (no LED-current names or command ids) |
| **Frames are shown 1:1 on the mirrors.** | `rig.safety.check_frame()`: exactly 1140 × 912 (mono or BGR), `uint8`. Anything else is refused before it reaches the window. The window warns if the display is not 912 × 1140 at the expected position. | `test_rig_safety.py` |
| **Hardware only through `rig/`.** | Outside `rig/` there is no PySpin, no OpenCV display window, and no direct `HDMIWindow`, `Camera` or `RigLock`. Scripts use `with rig.bench.Bench(...)` or the `open_rig()` pair, with `lock.release()` in a `finally`. | `test_static_safety.py` |
| **Leave the bench dark and free on every exit.** | `Bench.close()` shows a black frame, closes the window and the camera, then releases the lock, in `finally` blocks. This holds for errors, Ctrl+C and a failed camera open. | `test_rig_safety.py` |
| **No hardware from tests, CI or cloud sessions.** | `DLP_NO_HARDWARE=1` makes `Bench`, `HDMIWindow` and `Camera` refuse before touching the lock. The tests set it automatically, and CI sets it too. | `test_rig_safety.py` |

## Rules for people

- **Physical steps are Joey's:** moving or filling the case, aiming or focusing, cabling, the camera lens, and power.
- **Firmware, pattern and flash modes, and LED currents are set only by Joey,** in the EKB 4500 MKII GUI, after a firmware backup. `vol2/flashpack.py` and `vol2/subframe.py` only write files and a step list (`procedure.txt`). They send nothing to the projector.
- **Don't hold the rig longer than a capture session.** Players stop at their time limit or when a `STOP` file appears in the repo root. `STOPALL` also ends a playlist (`tools/demo_planes.ps1`).
- **Check the case didn't move before trusting a calibration.** Re-project the numbered grid (`tools/numgrid.py`), or re-run the column sweep, before playing warp-corrected scenes.
- **Eyes:** don't look into the projector lens. The blue LED is bright at close range.
- **Liquids:** keep the glycerin case and any spills away from the projector and the camera electronics.

## Stopping

- **Stop a running player:** create an empty file named `STOP` in the repo root:
  ```
  type nul > STOP
  ```
  You can also press Ctrl+C in its terminal. Either way the DMD goes dark and the lock is released.
- **If a process hangs:** close its window. When the process ends, the OS releases the lock.
- **Never** delete `rig.lock` or kill another program's process to get the rig.

## Changing `rig/`

`rig/` is the only layer that touches hardware. Changes to it, or to `tests/test_static_safety.py` and `tests/test_rig_safety.py`, need Joey's review. Never weaken a guard to make something work. If a guard blocks you, stop and ask.
