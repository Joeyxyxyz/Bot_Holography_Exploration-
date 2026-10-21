"""
End-to-end example: two glyphs at two depths, exported for the DLPC350.

    python3 examples/make_patterns.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from ogr import pipeline

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Layer separation must exceed the axial resolution (26.8 mm at z = 0.5 m).
# 0.50 m and 0.55 m are 50 mm apart: resolvable. Do not tighten without
# recomputing fresnel.axial_resolution for the aperture you actually use.
manifest = pipeline.run(
    glyphs=[pipeline.text_glyph("X", 512), pipeline.text_glyph("O", 512)],
    outdir=OUT,
    focal_lengths=[0.50, 0.55],
    encode_size=1024,
    f_c=0.125,
    axis="diag",
    stripe_width=3,
    gs_iters=30,
)
pattern = manifest.pop("_pattern")

print("pattern shape        ", pattern.shape)
print("ON fraction          ", round(float(pattern.mean()), 4))
print("glyph offset (m)     ", round(manifest["glyph_lateral_offset_m"], 5))
print("axial resolution (m) ", round(manifest["resolution"]["axial_resolution_m"], 4))
print("layer separation (m) ", 0.05)
print("files                ", manifest["files"])
print("written to           ", OUT)

sim = pipeline.simulate(pattern, crop=512)
np.save(os.path.join(OUT, "predicted_intensity.npy"), sim)
print("predicted intensity  ", "predicted_intensity.npy (512x512, normalised)")
print()
print("Compare any bench photograph against predicted_intensity.npy.")
print("Run the two baselines in docs/PREREGISTRATION.md before claiming a result.")
