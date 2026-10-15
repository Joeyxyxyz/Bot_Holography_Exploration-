"""GIFs from a shoot_bgr run: one per clip, cropped to the case, common brightness scale per clip.
  python tools/make_gif_dir.py <run_dir> [x0 y0 x1 y1]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

run = Path(sys.argv[1])
x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6]) if len(sys.argv) > 5 else (380, 380, 940, 820)
for f in sorted(run.glob("*.npz")):
    fr = np.load(f)["frames"].astype(np.float32)[:, y0:y1, x0:x1]
    top = np.percentile(fr, 99.8) or 1.0
    imgs = []
    for a in fr:
        im = Image.fromarray((np.clip(a / top, 0, 1) ** 0.6 * 255).astype(np.uint8)).resize((480, int(480 * a.shape[0] / a.shape[1])))
        ImageDraw.Draw(im).text((6, 6), f.stem, fill=255)
        imgs.append(im)
    out = run / f"{f.stem}.gif"
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=120, loop=0)
    print(out)
