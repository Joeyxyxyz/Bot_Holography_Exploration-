"""The scene catalogue as people see it: groups, friendly names, one-line descriptions, and which knobs apply.

Every scene in vol2.volplay.SCENES appears exactly once (tests/test_studio.py checks it). Descriptions follow
the scene code in vol2/volplay.py; "by eye" notes are Joey's 2026-10-05 observations [HEURISTIC]."""
from __future__ import annotations

from pathlib import Path

from vol2 import volplay

REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "docs" / "figures"

GROUPS = [
    {"id": "ribbons", "title": "Ribbons",
     "blurb": "Twisting light curtains from both faces. Best structure and animation by eye.",
     "scenes": [
         ("ribbon", "Ribbon", "Two twisting curtains of light, one from each face, sweeping through the liquid."),
         ("ribbon_fast", "Fast ribbon", "The ribbon at double speed."),
         ("ribbon_twist", "Twisted ribbon", "A full twist over the height of the liquid."),
         ("ribbon_double", "Double ribbon", "Two ribbons per face, half a cycle apart."),
         ("ribbon_cage", "Ribbon cage", "Three ribbons per face weaving a turning cage."),
     ]},
    {"id": "waves", "title": "Curtains & waves",
     "blurb": "Sheets of light designed directly on the mirrors; they do not depend on the case fit.",
     "scenes": [
         ("wave_A", "Rippling curtain", "One sheet of light from face A, rippling upward."),
         ("waves_AB", "Crossing curtains", "Rippling sheets from both faces; the line where they cross moves."),
         ("ocean_swell", "Gentle swell", "A slow rolling wave surface from face A."),
         ("ocean", "Ocean", "A layered wave surface from both faces."),
         ("ocean_storm", "Storm", "Tall, fast, choppy waves."),
     ]},
    {"id": "planes", "title": "Planes",
     "blurb": "Flat sheets of light. The thick ones span the full width, corner included.",
     "scenes": [
         ("fw_static", "Thick plane", "A strong, level sheet across the whole case."),
         ("fw_scan", "Scanning plane", "The thick sheet sweeps from top to bottom and back."),
         ("fw_stack", "Floors", "Floors light up one by one, hold, then fade."),
         ("fw_breathe", "Breathing plane", "The sheet's thickness and brightness breathe."),
         ("fw_rock", "See-saw", "The sheet tilts back and forth."),
         ("fw_ripple", "Ripple", "A calm ripple runs along a strong sheet."),
         ("fw_split", "Split", "One sheet splits into two and merges again."),
         ("fw_rain", "Rain", "Thin sheets fall from the top, one after another."),
         ("fw_ribbon", "Plane + ribbon", "A strong sheet with the twisting ribbon curtains through it."),
         ("plane_flat", "Thin plane", "A thin level sheet from both faces (corner left dark)."),
         ("plane_sweep", "Thin sweeping plane", "The thin sheet moves up and down."),
         ("plane_tilt", "Thin tilted plane", "A thin sheet at a slant."),
     ]},
    {"id": "corrected", "title": "Level from the camera",
     "blurb": "Planes bent on purpose so they look straight and level from the camera's spot (warp scan, "
              "2026-10-05). Only right if the case has not moved.",
     "scenes": [
         ("fwc_static", "Level plane", "A plane corrected to look flat from the camera position."),
         ("fwc_scan", "Level scan", "The corrected plane sweeps up and down."),
         ("fwc_stack", "Level floors", "Corrected floors build up one by one."),
         ("fwc_rock", "Level see-saw", "The corrected plane tilts back and forth."),
         ("fwc_ripple", "Level ripple", "A ripple on the corrected plane."),
         ("fwc_split", "Level split", "The corrected plane splits in two and merges."),
     ]},
    {"id": "solids", "title": "Solid shapes",
     "blurb": "Shapes built from crossing bands of light. They depend on the case fit, and every slice is a "
              "squashed diamond (the faces' rays cross at about 30 degrees).",
     "scenes": [
         ("ball_bounce", "Bouncing ball", "A solid ball bounces between top and bottom."),
         ("ball_pulse", "Pulsing ball", "The ball's brightness breathes once a second."),
         ("sphere_round", "Round sphere", "A sphere with softened edges (graded brightness)."),
         ("sphere_pulse", "Breathing sphere", "The sphere grows and shrinks."),
         ("sphere_bounce", "Bouncing sphere", "The soft sphere bounces top to bottom."),
         ("orbit", "Orbit", "A small ball circles the centre of the case."),
         ("tower_twist", "Twisting tower", "Slices orbit with height: a twisting column."),
         ("layer_scan", "Layer scan", "A bright slab sweeps down with a fading trail."),
     ]},
]

FAVOURITES = {"ribbon", "fw_static", "fw_ribbon"}      # Joey's picks by eye, 2026-10-05
SOLIDS = {s for g in GROUPS if g["id"] == "solids" for s, _, _ in g["scenes"]}
SIZE_SCENES = SOLIDS - {"orbit"}                         # orbit's ball has a fixed size in vol2/volplay.py
NEEDS_FIT = SOLIDS                                       # placement comes from the fitted case pose
NEEDS_WARP = {s for g in GROUPS if g["id"] == "corrected" for s, _, _ in g["scenes"]}

# the plane demo (tools/demo_planes.ps1): 10 scenes, 20 s each
DEMO = ["fwc_static", "fwc_scan", "fwc_stack", "fwc_split", "fwc_rock", "fwc_ripple", "fw_rain", "fw_ribbon",
        "fw_breathe", "ribbon"]


def camera_gif(scene: str):
    """A real stop-motion camera capture of this scene, if one was made (docs/figures/23_<scene>_camera.gif)."""
    p = FIGURES / f"23_{scene}_camera.gif"
    return p if p.is_file() else None


def scenes() -> dict:
    """scene id -> {id, title, description, group, period_s, favourite, size_knob, needs_fit, needs_warp, camera}"""
    out = {}
    for g in GROUPS:
        for sid, title, desc in g["scenes"]:
            out[sid] = {"id": sid, "title": title, "description": desc, "group": g["id"],
                        "period_s": volplay.PERIODS[sid], "favourite": sid in FAVOURITES,
                        "size_knob": sid in SIZE_SCENES, "needs_fit": sid in NEEDS_FIT,
                        "needs_warp": sid in NEEDS_WARP, "camera": camera_gif(sid) is not None}
    return out


def as_json() -> dict:
    sc = scenes()
    return {"groups": [{"id": g["id"], "title": g["title"], "blurb": g["blurb"],
                        "scenes": [s for s, _, _ in g["scenes"]]} for g in GROUPS],
            "scenes": sc, "demo": DEMO}
