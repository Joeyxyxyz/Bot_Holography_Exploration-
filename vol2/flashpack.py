"""
Pattern-mode pack: up to 16 one-bit frames (24 with allow_blue) in ONE 912x1140 24-bit BMP, for the
4500 MKII GUI.

Bit k of the packed pixel = slot k. Planes: bits 0-7 -> G0-G7 (green byte), 8-15 -> R0-R7 (red byte),
16-23 -> B0-B7 (blue byte). Same convention as the scanner's flash fast-scan pack
(docs/FLASH_FASTSCAN_4500.md §4, DLPU010G Table 2-70). Standard BMP: bottom-up rows, B-G-R bytes.
The GUI may name G/R the other way round. With exactly 16 slots (G0-G7, R0-R7, B unused) the unit then
plays 8-15, 0-7: the same repeating loop rotated by 8 slots. Only then is it a pure rotation: with 24
slots a swap plays 8-15, 0-7, 16-23 (scrambled), and with fewer than 16 it plays black or misplaced
frames. So an animation pack stops at 16 slots unless allow_blue=True, and every pack carries a plane
check (plane_check_16bit.bmp: slot k shows the big digit k) that shows which case the unit is in
before the animation plays.

WRITES FILES ONLY. Nothing here talks to the projector: flashing, entering pattern mode, exposure /
period, Play / Stop and returning to video mode are Joey's, in the GUI, after a firmware backup
(FLASH_FASTSCAN_4500.md §5.1; the click list for each pack is its procedure.txt). Nothing has been
run on the rig.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

H, W = 1140, 912
MAX_GR = 16                                            # G0-G7 + R0-R7: a G/R swap is a pure rotation
LED_START = (35, 50, 45)                               # R, G, B: the HDMI bench values (doc §5.1, §5.5)
LED_LIMIT = (120, 180, 160)                            # continuous-limit GUI build; never short-burst
LED_HOT = (40, 60, 53)                                 # ~limit / 3: pattern mode keeps the LED on the
                                                       # whole exposure, ~3x its video-mode duty
DOC = "https://github.com/Joeyxyxyz/swiss-army-scanner/blob/main/docs/FLASH_FASTSCAN_4500.md"


def plane_name(k):
    return f"G{k}" if k < 8 else f"R{k - 8}" if k < 16 else f"B{k - 16}"


def pack(frames):
    if not 1 <= len(frames) <= 24:
        raise ValueError("1..24 frames per 24-bit image")
    val = np.zeros((H, W), np.uint32)
    for k, f in enumerate(frames):
        if f.shape != (H, W):
            raise ValueError(f"frame {k} is {f.shape}, need {(H, W)}")
        val |= ((f > 0).astype(np.uint32) << k)
    g = (val & 0xFF).astype(np.uint8)
    r = ((val >> 8) & 0xFF).astype(np.uint8)
    b = ((val >> 16) & 0xFF).astype(np.uint8)
    return np.dstack([b, g, r])                        # OpenCV BGR order -> BMP B, G, R bytes


def unpack(bgr, n):
    b, g, r = (bgr[..., i].astype(np.uint32) for i in range(3))
    val = g | (r << 8) | (b << 16)
    return [((val >> k) & 1).astype(np.uint8) * 255 for k in range(n)]


def digit_frame(k):
    """Plane-check frame for slot k: the big digit k and a small "slot k = <plane>" caption, mono 0/255.
    Drawn at 912x570 and doubled in rows: the diamond DMD's 1140 rows sit at half the column pitch, so
    this is what reads with the right aspect on the wall (mirrored / upside down with the mounting)."""
    c = np.zeros((H // 2, W), np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(str(k), font, 13, 40)
    cv2.putText(c, str(k), ((W - tw) // 2, 65 + th), font, 13, 255, 40, cv2.LINE_8)   # LINE_8: no grey
    cap = f"slot {k} = {plane_name(k)}"
    (cw, _), _ = cv2.getTextSize(cap, font, 2.0, 5)
    cv2.putText(c, cap, ((W - cw) // 2, 540), font, 2.0, 255, 5, cv2.LINE_8)
    return cv2.resize(c, (W, H), interpolation=cv2.INTER_NEAREST)


def _write_bmp(p: Path, frames):
    cv2.imwrite(str(p), pack(frames))
    back = cv2.imread(str(p), cv2.IMREAD_COLOR)
    rt = all(np.array_equal(a > 0, b > 0) for a, b in zip(frames, unpack(back, len(frames))))
    return {"image": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "round_trip_from_disk_ok": bool(rt)}


def _write_singles(d: Path, frames, names):
    d.mkdir(exist_ok=True)
    for old in d.glob("slot*.bmp"):                    # a rebuild with fewer slots leaves no stale ones
        old.unlink()
    for k, f in enumerate(frames):
        f = (f > 0).astype(np.uint8) * 255
        cv2.imwrite(str(d / f"slot{k:02d}{names[k]}.bmp"), np.dstack([f, f, f]))


def write_pack(out: Path, frames, names, exposure_us=None, note="", allow_blue=False):
    n = len(frames)
    if n > MAX_GR and not allow_blue:
        raise ValueError(f"{n} frames: an animation pack is at most {MAX_GR} slots (G0-G7, R0-R7) so that "
                         "a GUI G/R swap is a pure rotation of the loop; allow_blue=True for up to 24")
    out.mkdir(parents=True, exist_ok=True)
    main = _write_bmp(out / "pack_24bit.bmp", frames)
    _write_singles(out / "singles", frames, [f"_{s}" for s in names])
    nc = MAX_GR if n <= MAX_GR else 24                 # the check always covers every G and R plane
    digits = [digit_frame(k) for k in range(nc)]
    chk = _write_bmp(out / f"plane_check_{nc}bit.bmp", digits)
    _write_singles(out / "plane_check", digits, [""] * nc)
    chk.update({"singles": "plane_check/slotNN.bmp", "slots": nc,
                "expect": "GUI plane G1 shows 1, R0 shows 8" + (", B0 shows 16" if nc > 16 else "")})
    planes = [plane_name(k) for k in range(n)]
    man = {**main, "size": [W, H],
           "bits_per_pixel": 24, "slots": [{"slot": k, "plane": planes[k], "name": names[k]}
                                            for k in range(n)],
           "gr_swap_is_pure_rotation": n == MAX_GR, "plane_check": chk,
           "gui_image_order": {"N": main["image"], "N+1": chk["image"]},
           "suggested_exposure_us": exposure_us, "loop_ms": n * exposure_us / 1000 if exposure_us else None,
           "bit_depth": 1, "note": note,
           "procedure": "procedure.txt in this folder: Joey, 4500 MKII GUI (continuous-limit build), "
                        "back up first; files only, nothing was run on the rig"}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    (out / "procedure.txt").write_text(procedure_text(out, man), encoding="utf-8")
    return man


def procedure_text(out: Path, m) -> str:
    """The GUI click list for this pack: FLASH_FASTSCAN_4500.md §5.0-5.9, with this pack's files."""
    n, chk = len(m["slots"]), m["plane_check"]
    e = m["suggested_exposure_us"]
    exp = f"{e}" if e else "<same value in both, >= 235>"
    (r0, g0, b0), (rl, gl, bl), (rh, gh, bh) = LED_START, LED_LIMIT, LED_HOT
    L = [f"VOL2 ANIMATION PACK  {out}", "=" * 76, "",
         "Written by vol2/flashpack.py.",
         "FILES ONLY: nothing was run on the rig and nothing was sent to the projector.",
         "Every GUI step below is Joey's, in the 4500 MKII GUI build for the CONTINUOUS LED",
         "limits (the one labelled R120 G180 B160), not the short-burst build.",
         f"Full guide with the reasons: {DOC}",
         "section 5; this list follows 5.0-5.9 step by step with this pack's files.", "",
         "Files in this folder:",
         f"  {m['image']:<24} the animation: {n} one-bit frames, slot k = bit k"
         + (" (G0-G7, R0-R7; B unused)" if n <= MAX_GR else ""),
         f"  {chk['image']:<24} the plane check: slot k shows the big digit k, same layout",
         "  plane_check/slotNN.bmp   the digits one by one;  singles/ = the frames one by one",
         "  manifest.json            slot -> plane -> frame, sha256, round-trip result", ""]
    if not (m["round_trip_from_disk_ok"] and chk["round_trip_from_disk_ok"]):
        L += ["!! STOP: an image did not unpack to its frames after reading it back from disk.", ""]
    if n != MAX_GR:
        L += [f"!! This pack has {n} slots, not 16: a GUI G/R swap is NOT a pure rotation of the loop.",
              "   The plane check (step 4) must pass, or the rows must be re-entered as it says.", ""]
    L += ["0. BEFORE YOU START",
          "   - HDMI scan idle: no other program holds the rig lock.",
          "     Modes are changed only here, in the GUI, and never mid-scan.",
          "   - Once per unit / per new .bin: steps 1, 2 and 4. After that a viewing session is",
          "     3 -> 5 -> 6 -> 7.", "",
          "1. BACK UP FIRST (nothing is changed yet)",
          "   - System Control: write down the Firmware Version and the Firmware Tag.",
          "   - LED Driver Control: write down the LED Current R / G / B (HDMI bench preset:",
          f"     R{r0} G{g0} B{b0}).",
          "   - Save Solution: save a .ini of today's video-mode settings next to your notes.",
          "   - Image / Firmware tab -> the firmware link (\"Download the latest Firmware release",
          "     from ...\": the DLPC350 / DLPR350 firmware page). Download the firmware .bin and keep",
          "     it with the .ini. Its version MUST equal the Firmware Version written down above.",
          "     If it differs, STOP HERE: the unit runs its supplier's firmware, so the base for",
          "     step 2 and the rollback image must be the supplier's .bin. If the unit came with",
          "     its own firmware .bin, use that file as the base and rollback image in any case.",
          "   - The GUI can write the flash but cannot read it back: the saved .bin IS the backup.",
          "     Do not go on without it.",
          "   - If the Firmware Tag is not the factory one (e.g. fastscan1bit from the swiss-army-scanner",
          "     fast-scan pack), the flash already holds added images: use the .bin that was",
          "     uploaded then as the base in step 2 so they stay, and keep the factory .bin as",
          "     the full rollback.", "",
          "2. PUT THE IMAGES INTO FLASH (Image / Firmware -> Firmware Build)",
          "   a. Firmware File: Browse -> the backup .bin from step 1 (or, with a non-factory tag,",
          "      the .bin uploaded then). Note \"# Original Images\" = N.",
          "   b. Add these 24-bit 912x1140 BMPs AFTER the original images, in this order (Add;",
          "      Change / Remove act on the image selected in the index list):",
          f"        {m['image']:<24} -> flash index N     (the animation)",
          f"        {chk['image']:<24} -> flash index N+1   (the plane check)",
          "      \"Images Added\" must read 2 and \"Total Images\" N + 2. Keep ALL the original images:",
          "      the splash / default images are still needed for video mode. Packing can",
          "      renumber images; the plane check (step 4) confirms the index.",
          "   c. Add Firmware Tag: e.g. vol2cube (32 characters at most).",
          "   d. Illumination Control: RGB Color.  Select .ini File: leave empty.",
          "   e. Save Updates -> a NEW .bin name. Never overwrite the backup: keep the original",
          "      .bin and .ini untouched.",
          "   Image / Firmware -> Firmware Upload:",
          "   f. Browse -> the new .bin. Tick Skip Bootloader Update (the 128 KB bootloader stays",
          "      untouched, so an interrupted upload can be retried over USB). Leave Fast Flash",
          "      Update unticked for the first upload.",
          "   g. Upload. The flash is erased, then rewritten: wait for the end. Do not unplug USB,",
          "      power off or close the GUI.",
          "   h. After the unit reconnects: System Control shows the new Firmware Tag. Video mode",
          "      still shows the HDMI desktop, and the LED currents match step 1 (fix them in LED",
          "      Driver Control if not).",
          "   (The Download Pattern button has not been tried here; the .bin route is the documented",
          "   one.)", "",
          "3. PATTERN SEQUENCE SETTINGS (Sequence Settings)",
          "   Operating Mode: Pattern Sequence (not the variable-exposure mode).",
          "   Pattern Source: Flash        Trigger Mode: Internal/External",
          f"   Pattern Exposure (us): {exp}    Pattern Period (us): {exp}",
          "   (equal exposure and period: legal for 1-bit, no dark gap between frames)",
          "   Clear the pattern list, then for EACH row below, in this order:",
          "     Choose Color: Blue (fluorescein / highlighter fill glows under blue; one LED, least",
          "     heat). Use White only for a milk-only (scattering) fill.",
          "     Internal Trigger     Image Index: N     Bit Depth: 1     Bit Plane: the row's plane",
          "     Invert Pattern Data: off     Clear DMD after exposure: off",
          "     -> Add Pattern to Sequence", "",
          "      row  plane  frame"]
    L += [f"     {s['slot']:4d}  {s['plane']:<5}  {s['name']}" for s in m["slots"]]
    L += ["",
          "   Play Once: OFF (the loop repeats until Stop). Send -> Validate Sequence: every Data",
          "   Validation indicator clear, \"Sequence Validated\"."]
    if m["loop_ms"]:
        L.append(f"   Loop = {n} x {e} us = {m['loop_ms']:g} ms." + (f"  ({m['note']})" if m["note"] else ""))
    L += ["   Save Solution (optional): vol2_cube.ini -> next time Apply Solution sets it all up.",
          "   On a new unit / new .bin do step 4 BEFORE playing this sequence.", "",
          "4. PLANE CHECK (once per unit / per new .bin, before the first Play of the animation)",
          "   A ONE-pattern sequence: Image Index N+1, Bit Depth 1, Bit Plane G1, Pattern Exposure =",
          f"   Pattern Period = {exp} us, Play Once off. Send, Validate, Play (one pattern on",
          "   repeat = a still image). Stop, then the same with Bit Plane R0"
          + (", then B0." if chk["slots"] > 16 else "."),
          "   The digit may look mirrored or upside down with the mounting; that is fine. The",
          "   small caption under it names the plane this pack meant for that digit.",
          "     G1 \"1\", R0 \"8\"" + (", B0 \"16\"" if chk["slots"] > 16 else "")
          + "  = the planes are as this pack assumes. Go on.",
          "     G1 \"9\", R0 \"0\"  = the GUI reads G and R the other way round."]
    if n == MAX_GR:
        L += ["                      With these 16 rows that is the same loop started 8 frames later",
              "                      (a pure rotation, harmless for a repeating animation): note it.",
              "                      To play it in order anyway, enter the rows with G and R",
              "                      exchanged (slots 0-7 on R0-R7, slots 8-15 on G0-G7)."]
    else:
        L += [f"                      With {n} slots that scrambles the loop: enter the rows with G",
              "                      and R exchanged (slot k < 8 on R k, slot 8 + j on G j)."]
    L += ["     G1 \"6\", R0 \"15\" = the bits are reversed inside the byte: enter the rows with",
          "                      planes G7 ... G0, R7 ... R0 (slot k on G(7-k), slot 8+j on R(7-j)).",
          "     In general: the digit a GUI plane shows is the slot that plane plays; row k of",
          "     step 3 must use the plane that showed the digit k.",
          "     R0 black         = the GUI's R is not the BMP's red byte: compose the image in the",
          "                      GUI's Image / Firmware -> Create Images from singles/ (slot k at",
          "                      bit position k, bit depth 1) and redo step 2 with it.",
          "     A cube frame     = that is the animation image: the index is off (renumbered);",
          "                      step the Image Index until G1 shows the digit 1.",
          "     A splash image / all black = wrong Image Index: step it until G1 shows the digit 1.",
          "   Stop, then build the sequence of step 3 on Image Index N. If the digits were not on",
          "   N+1, use the index where a one-pattern Play on G0 shows a cube frame.", "",
          "5. LED CURRENTS (LED Driver Control -> LED Current)",
          f"   Start at R{r0} G{g0} B{b0} (the HDMI bench values) -> Set. Raise only if the volume",
          "   is too dim.",
          f"   HARD LIMIT: the continuous limits R{rl} G{gl} B{bl}. The short-burst values (R180",
          "   G255 B230, short-burst GUI only) are NEVER used for a repeating loop.",
          "   Pattern mode can keep the chosen LED on for the whole exposure, i.e. a higher duty than",
          f"   in video mode [HEURISTIC, not measured]. Above about R{rh} G{gh} B{bh}, raise in small",
          "   steps and watch the unit's temperature; never above the continuous limits.",
          "   STOP THE SEQUENCE WHENEVER NOBODY IS VIEWING.", "",
          "6. PLAY: Pattern Sequence Start/Stop/Pause -> Play. The controller plays the loop from",
          "   its own memory; nothing runs on the PC. Stop when not viewing and before any change.", "",
          "7. BACK TO HDMI VIDEO MODE (always, before any HDMI scan or HDMI content)",
          "   a. Stop the sequence.",
          "   b. Operating Mode: Video Mode.",
          "   c. Input Configuration -> Source Select: Parallel RGB (the HDMI input).",
          "   d. Check that the laptop desktop is on the DMD.",
          "   e. LED Current back to the values from step 1 -> Set.",
          "   f. Only now run HDMI scans.",
          "   Blue lines or the internal test pattern instead of the desktop: follow the scanner's",
          "   docs/HDMI_TIMING_FIX.md (so far only a power cycle recovered it). Mode switches are",
          "   what triggers it, so switch rarely: batch the viewing.", "",
          "8. ROLLBACK (to take the added images out again)",
          "   a. Image / Firmware -> Firmware Upload -> Browse -> the backup .bin from step 1.",
          "   b. Tick Skip Bootloader Update, then Upload. Wait for the end.",
          "   c. System Control shows the original Firmware Version and Firmware Tag.",
          "   d. Video Mode, then Apply Solution with the step-1 .ini (or re-enter the LED currents).",
          "   If the unit no longer connects over USB after a failed upload: the bootloader was not",
          "   touched (Skip Bootloader Update), so power-cycle and upload the backup again. JTAG is",
          "   the last resort; do not attempt it without the supplier.", ""]
    return "\n".join(L)
