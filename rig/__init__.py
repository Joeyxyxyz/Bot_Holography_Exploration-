"""
Bench hardware layer: DLP LightCrafter 4500 over HDMI + FLIR Blackfly S camera + the shared rig lock.

MACHINE SAFETY (see SAFETY.md) is enforced here, not left to callers:
  * one program drives the rig at a time: every hardware entry point takes the machine-wide rig lock
    (the same OS lock file as Joey's swiss-army-scanner, so the two tools exclude each other);
  * HDMI video mode only: this package never sends USB/HID commands to the DLPC350 and refuses to run
    if a USB/HID module is loaded in the process;
  * LED currents are never touched (there is no LED code here at all);
  * frames are shown 1:1 on the mirrors (exact 1140 x 912 required; the window refuses to open unless it is
    exactly the DMD display);
  * on every exit path the DMD is blanked, the window and camera closed, then the lock released.
Everything else in this repository (models, rendering, simulation, tests) runs WITHOUT hardware.
"""
