"""
ogr.bmp — write DMD patterns as BMP files the DLPC350 / LightCrafter 4500 GUI
will accept. Pure stdlib + numpy, no Pillow required.

The TI LightCrafter 4500 GUI loads 912 x 1140 BMPs for Pattern Sequence mode.
It reliably accepts 24-bit BMPs and selects bit-planes from them; 1-bit BMPs
are smaller and unambiguous but some GUI versions reject them. Write both and
use whichever the GUI on the bench accepts — `write_pattern` does both by
default.

Pattern-sequence timing constraints (TI DLPU011E):
  1-bit pattern, minimum exposure  235 us   -> max 4225 Hz
  8-bit pattern, minimum exposure 8333 us   -> max  120 Hz
  Exposure must be >= the pre-exposure dark time plus the illumination time.
"""

import struct
import numpy as np


def _pad4(n):
    return (4 - (n % 4)) % 4


def write_bmp1(path, pattern):
    """
    Write a 1-bit-per-pixel BMP. `pattern` is a 2-D array of 0/1.
    Rows are stored bottom-up, MSB first, each row padded to 4 bytes.
    """
    a = (np.asarray(pattern) != 0).astype(np.uint8)
    h, w = a.shape
    row_bytes = (w + 7) // 8
    pad = _pad4(row_bytes)
    stride = row_bytes + pad

    packed = np.packbits(a, axis=1)                     # (h, row_bytes)
    if packed.shape[1] < row_bytes:
        packed = np.pad(packed, ((0, 0), (0, row_bytes - packed.shape[1])))
    rows = np.zeros((h, stride), dtype=np.uint8)
    rows[:, :row_bytes] = packed
    pixels = rows[::-1].tobytes()                        # bottom-up

    palette = struct.pack("<BBBB", 0, 0, 0, 0) + struct.pack("<BBBB", 255, 255, 255, 0)
    offset = 14 + 40 + len(palette)
    filesize = offset + len(pixels)

    with open(path, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<IHHI", filesize, 0, 0, offset))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 1, 0,
                            len(pixels), 2835, 2835, 2, 2))
        f.write(palette)
        f.write(pixels)
    return path


def write_bmp24(path, pattern, channel="all"):
    """
    Write a 24-bit BMP. `pattern` is 0/1; ON becomes 255 in the selected
    channel(s). channel in {"all", "r", "g", "b"} — use a single channel when
    you want the GUI to map one bit-plane to one LED.
    """
    a = (np.asarray(pattern) != 0).astype(np.uint8) * 255
    h, w = a.shape
    img = np.zeros((h, w, 3), dtype=np.uint8)            # BGR order in BMP
    idx = {"b": 0, "g": 1, "r": 2}
    if channel == "all":
        img[..., 0] = img[..., 1] = img[..., 2] = a
    else:
        img[..., idx[channel]] = a

    row_bytes = w * 3
    pad = _pad4(row_bytes)
    rows = np.zeros((h, row_bytes + pad), dtype=np.uint8)
    rows[:, :row_bytes] = img.reshape(h, row_bytes)
    pixels = rows[::-1].tobytes()

    offset = 14 + 40
    filesize = offset + len(pixels)
    with open(path, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<IHHI", filesize, 0, 0, offset))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                            len(pixels), 2835, 2835, 0, 0))
        f.write(pixels)
    return path


def read_bmp1(path):
    """Read back a 1-bit BMP written by write_bmp1. Round-trip test helper."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"BM":
        raise ValueError("not a BMP")
    offset = struct.unpack("<I", data[10:14])[0]
    w, h = struct.unpack("<ii", data[18:26])
    bpp = struct.unpack("<H", data[28:30])[0]
    if bpp != 1:
        raise ValueError("expected 1 bpp, got %d" % bpp)
    row_bytes = (w + 7) // 8
    stride = row_bytes + _pad4(row_bytes)
    raw = np.frombuffer(data[offset:offset + stride * h], dtype=np.uint8)
    raw = raw.reshape(h, stride)[:, :row_bytes]
    bits = np.unpackbits(raw, axis=1)[:, :w]
    return bits[::-1]


def write_pattern(stem, pattern, both=True, channel="all"):
    """Write `stem`.bmp (1-bit) and, if both, `stem`_24.bmp."""
    out = [write_bmp1(stem + ".bmp", pattern)]
    if both:
        out.append(write_bmp24(stem + "_24.bmp", pattern, channel=channel))
    return out


PATTERN_SEQUENCE_LIMITS = {
    "bit_depth_1_min_exposure_us": 235,
    "bit_depth_1_max_rate_hz": 4225,
    "bit_depth_8_min_exposure_us": 8333,
    "bit_depth_8_max_rate_hz": 120,
    "native_width": 912,
    "native_height": 1140,
    "note": "TI DLPU011E. Exposure must cover dark time plus illumination.",
}
