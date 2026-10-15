"""Turn a shoot_set run of animation frames into a background-subtracted, cropped animated GIF.
  python tools/make_gif.py <run_dir> <exposure_us> [x0 y0 x1 y1]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

run, exp = Path(sys.argv[1]), sys.argv[2]
x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7]) if len(sys.argv) > 6 else (420, 300, 900, 780)
z = np.load(run / "raw.npz")
black = z[f"black_{exp}us"].astype(np.float32)
keys = sorted(k for k in z.files if k.endswith(f"_{exp}us") and not k.startswith("black"))
imgs = [np.clip(z[k].astype(np.float32) - black, 0, None)[y0:y1, x0:x1] for k in keys]
top = max(np.percentile(a, 99.8) for a in imgs) or 1.0
frames = [Image.fromarray((np.clip(a / top, 0, 1) ** 0.6 * 255).astype(np.uint8)).resize((400, 400)) for a in imgs]
out = run / "camera_animation.gif"
frames[0].save(out, save_all=True, append_images=frames[1:], duration=100, loop=0)
print(out, len(frames), "frames")
