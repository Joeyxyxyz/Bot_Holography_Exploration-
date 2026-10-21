"""
Holo Studio: a simple local web UI for playing the volumetric scenes in the fluorescent case.

    python -m studio                 # opens http://127.0.0.1:8765 in the browser
    python -m studio --no-browser --port 8800

Pick a scene, watch its preview, set duration / speed / brightness / size, press Play; STOP is always on screen.
Everything that touches the projector goes through rig/ (vol2.volplay.play -> rig.bench.Bench): the shared rig
lock, HDMI only, no LED or USB/HID code, DMD blanked and lock released on every exit (see SAFETY.md).

With DLP_NO_HARDWARE=1 (tests, CI, cloud sessions, or just trying it out) the studio is preview-only: scenes
render and simulate, but Play is refused. The server listens on 127.0.0.1 only and every API call needs the
per-launch token the page carries, so other web pages cannot drive the projector.
"""
