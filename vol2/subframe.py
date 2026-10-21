"""
1440 Hz sub-frames over HDMI: Geng's "bit-plane splitting" with the DLPC350's own video-port pattern mode.

In Pattern Sequence mode with Pattern Source = Video port and Trigger = VSYNC (Joey, 4500 MKII GUI), each 60 Hz
HDMI frame's 24 bit-planes are shown as 24 one-bit patterns, one after another (DLPU011E 3.3.1; Table 4-1 allows
1-bit video-port patterns up to 2880 Hz). With 24 patterns per 16.667 ms frame each sub-frame lasts ~694 us.
This module samples a volplay scene 1440 times per second, renders each sample as a 1-bit frame, and packs 24
consecutive sub-frames into one 24-bit HDMI frame (bit k -> slot k; G0-G7, R0-R7, B0-B7 like flashpack.pack).
Duty: an element with duty d is lit in round(24 d) of each frame's 24 sub-frames, chosen by a spread
(bit-reversed) order, so duty is linear (no video-mode dead zone).
In a linear medium the eye sums the sub-frames: speed buys smooth motion and linear duty, not ghost removal.
Writes: frames/fNNNN.png (play with: python -m vol2.subframe play <dir>), plane_check.png, procedure.txt.
FILES ONLY until Joey switches the mode; in Video Mode these frames look like coloured noise.

  python -m vol2.subframe build <scene> [--seconds 2] [--mode ab|b]
  python -m vol2.subframe play <out_dir> [--seconds 30]
  python -m vol2.subframe planecheck
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .flashpack import digit_frame, pack
from .render import H, W
from .volplay import ROOT, Volume, _period, play, scene_fn

SUB = 24                                  # sub-frames per HDMI frame
FPS = 60.0
SUB_HZ = SUB * FPS                        # 1440
OUT = ROOT / "vol2" / "out" / "subframe"
# Spread keys: the 5-bit bit reversals of 0..23 (values up to 30, so NOT slot numbers). Only their ranks are
# used: slot k gets threshold rank argsort(_ORDER)[k], so a growing duty lights slots 0, 12, 6, 18, 3, 15, ...
_ORDER = np.argsort([int(f"{k:05b}"[::-1], 2) for k in range(32)])[:SUB]
_THR = (np.argsort(_ORDER) + 0.5) / SUB           # slot k's duty threshold, spread over the frame


def raster_binary(elements, duty_slot, wc=3, wr=5):
    """1-bit frame: an element is ON in this sub-frame if its duty exceeds this slot's threshold."""
    f = np.zeros((H, W), np.uint8)
    for mirrors, d, _ in elements:
        if d <= duty_slot:
            continue
        for c, r in mirrors:
            f[max(0, r - wr // 2):min(H, r + wr // 2 + 1), max(0, c - wc // 2):min(W, c + wc // 2 + 1)] = 255
    return f


def subframes(vol, fn, i):
    """The 24 one-bit sub-frames of HDMI frame i: slot k samples the scene at t = i/60 + k/1440."""
    subs = []
    for k in range(SUB):
        els = fn((i * SUB + k) / SUB_HZ)
        if els:                                       # absorption compensation, normalised per sub-frame
            comp = np.array([d * np.exp(tau / vol.L) for _, d, tau in els])
            comp = comp / comp.max()
            els = [(m, float(c), tau) for (m, _, tau), c in zip(els, comp)]
        subs.append(raster_binary(els, _THR[k]))
    return subs


def build(scene, seconds=None, mode="ab", L=30.0, where=(40.0, 40.0)):
    vol = Volume(str(ROOT / "configs" / "case_fit_tank_v4.json"), where=where, mode=mode, L=L)
    fn = scene_fn(vol, scene)
    period = seconds or _period(scene)
    n_frames = int(round(period * FPS))
    out = OUT / f"{scene}_{mode}"
    (out / "frames").mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    for i in range(n_frames):
        cv2.imwrite(str(out / "frames" / f"f{i:04d}.png"), pack(subframes(vol, fn, i)))
    info = {"scene": scene, "mode": mode, "hdmi_frames": n_frames, "subframes": n_frames * SUB,
            "subframe_hz": SUB_HZ, "subframe_us": round(1e6 / SUB_HZ, 1), "render_s": round(time.perf_counter() - t0, 1)}
    (out / "info.json").write_text(json.dumps(info, indent=1))
    (out / "procedure.txt").write_text(procedure(out), encoding="utf-8")
    print(json.dumps(info))
    return out


def plane_check():
    """Packed 24-slot digit frame, written as a one-frame clip so `subframe play` (raw BGR) can show it.
    Do NOT use play_loop.py for it: that reads frames as grayscale and would destroy the bit-planes."""
    out = OUT / "plane_check"
    (out / "frames").mkdir(parents=True, exist_ok=True)
    img = pack([digit_frame(k) for k in range(SUB)])
    cv2.imwrite(str(out / "plane_check.png"), img)
    cv2.imwrite(str(out / "frames" / "f0000.png"), img)
    print(out)
    return out


def procedure(out: Path) -> str:
    exp = int(1e6 / SUB_HZ) - 4                     # 690 us: inside the 694 us slot
    return "\n".join([
        f"VIDEO-PORT PATTERN MODE (1440 sub-frames/s) for {out}",
        "Written by the DMD experiments session. Files only; every GUI step is Joey's (4500 MKII GUI, continuous-",
        "limit build). The HDMI desktop stays connected: in this mode the 24 bit-planes of each 60 Hz HDMI frame",
        "are shown as 24 one-bit patterns. Our player keeps feeding those frames.",
        "",
        "0. Back up first if you have not: Save Solution (.ini) of today's video-mode settings.",
        "1. Pattern Sequence settings:",
        "     Operating Mode: Pattern Sequence      Pattern Source: Video port      Trigger: VSYNC",
        f"     24 patterns, in this order: G0..G7, R0..R7, B0..B7 (Frame Index 0), Bit Depth 1,",
        f"     LED: Blue for every pattern, Pattern Exposure = Pattern Period = {exp} us (24 x {exp} us fits 16.667 ms),",
        "     Invert off, Clear DMD after exposure off. Validate Sequence -> 'Sequence Validated'.",
        "     Video input must be 912x1140 at 60 Hz (it is: our window).",
        "2. PLANE CHECK first: on the PC run",
        "     python -m vol2.subframe planecheck        (once, writes the packed digit frame)",
        "     python -m vol2.subframe play vol2\\out\\subframe\\plane_check --seconds 600",
        "   (raw BGR player; NOT play_loop.py, which reads grayscale and would destroy the bit-planes)",
        "   then Play. You should see the digits 0..23 flicker through. If you see 8..15 first, the GUI reads G/R",
        "   the other way: enter the rows as R0..R7, G0..G7, B0..B7 instead.",
        "3. Content: python -m vol2.subframe play <this folder>   then Play in the GUI if not already playing.",
        "4. LED current: start at the bench values (R35 G50 B45); blue is lit for every sub-frame, so it runs",
        "   hotter than in video mode [HEURISTIC]. Never above the continuous limit (B160). Stop when not viewing.",
        "5. Back to Video Mode in the GUI before any normal HDMI content, scan or capture.",
    ])


def play_dir(d: Path, seconds=30.0):
    files = sorted((d / "frames").glob("f*.png"))
    frames = [cv2.imread(str(f), cv2.IMREAD_COLOR) for f in files]
    res = play(frames, FPS, seconds)
    print(json.dumps(res))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("scene")
    b.add_argument("--seconds", type=float, default=None)
    b.add_argument("--mode", default="ab", choices=["ab", "b"])
    p = sub.add_parser("play")
    p.add_argument("dir", type=Path)
    p.add_argument("--seconds", type=float, default=30.0)
    sub.add_parser("planecheck")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.scene, a.seconds, a.mode)
    elif a.cmd == "play":
        play_dir(a.dir, a.seconds)
    else:
        plane_check()
