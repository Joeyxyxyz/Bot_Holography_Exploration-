"""
Numbered grid over the case: columns numbered 1.. across, rows lettered A.. down, every cell
labelled "<col><row>" (e.g. 7C). Cells 28 DMD cols x 49 rows (~10 mm at the case, 2.8 col/mm,
4.9 row/mm). Spans the front face, the rounded corner and the side face
(empty-case scan: front ~cols 470-605, side ~cols 612-710).
Text is drawn 2x tall: the diamond DMD's rows are half-pitch, so it lands roughly square.

  python tools/numgrid.py          -> runs/<ts>_numgrid/dmd_numgrid.png (then hold it with holo/holo_show.py)
"""
import sys
from pathlib import Path
import datetime as dt
import json

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from rig import bench as vm

C_START, CELL_C, NC = 432, 28, 11
R_START, CELL_R, NR = 575, 49, 10


def numgrid():
    img = np.zeros((vm.H, vm.W), np.uint8)
    xs = [C_START + i * CELL_C for i in range(NC + 1)]
    ys = [R_START + j * CELL_R for j in range(NR + 1)]
    for x in xs:
        img[ys[0]:ys[-1] + 1, x:x + 2] = 255
    for y in ys:
        img[y:y + 3, xs[0]:xs[-1] + 2] = 255
    for i, x in enumerate(xs[:-1]):
        for j, y in enumerate(ys[:-1]):
            label = f"{i + 1}{chr(65 + j)}"
            txt = np.zeros((14, 26), np.uint8)
            cv2.putText(txt, label, (0, 11), cv2.FONT_HERSHEY_PLAIN, 0.8, 255, 1)
            t = cv2.resize(txt, (26, 28), interpolation=cv2.INTER_NEAREST)
            y0, x0 = y + 8, x + 2
            img[y0:y0 + 28, x0:x0 + 26] = np.maximum(img[y0:y0 + 28, x0:x0 + 26], t)
    return img, xs, ys


def main():
    img, xs, ys = numgrid()
    run = vm.OUT / (dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "_numgrid")
    run.mkdir(parents=True)
    cv2.imwrite(str(run / "dmd_numgrid.png"), img)
    (run / "meta.json").write_text(json.dumps(
        {"col_edges_dmd": xs, "row_edges_dmd": ys,
         "cells": {f"{i + 1}{chr(65 + j)}": {"cols": [xs[i], xs[i + 1]], "rows": [ys[j], ys[j + 1]]}
                   for i in range(NC) for j in range(NR)}}, indent=1))
    print(run / "dmd_numgrid.png")


if __name__ == "__main__":
    main()
