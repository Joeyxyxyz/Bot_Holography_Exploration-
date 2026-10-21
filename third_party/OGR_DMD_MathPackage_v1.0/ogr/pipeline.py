"""
ogr.pipeline — glyph in, DMD pattern set out.

    glyph image (real, >= 0)
      -> optional per-layer Fresnel lens phase        (axial placement)
      -> sum of layers                                 (complex field)
      -> Lee binary encoding with carrier f_c          (lateral order offset)
      -> diagonal OFF-stripe reference overlaid        (z = 0 marker)
      -> padded / cropped to 912 x 1140                (native DMD frame)
      -> BMP files + JSON manifest                     (DLPC350 ingest)

Every stage is separately testable. The manifest records every parameter so
a run can be replayed exactly, which is the point of shipping this as a
package rather than a script.
"""

import json
import os
import numpy as np

from . import bmp, fresnel, lee
from .diagonal import diagonal_stripe
from .fourier import recon_report, reconstruct, intensity
from .hardware import DLP4500, LED_RED, OGR_GEOMETRY


def hologram_from_target(target, seed=0):
    """
    Stage 0 — the step that is easy to get backwards.

    The reconstruction is F[pattern]. To make F[pattern] look like the glyph
    you must encode H = F^-1[glyph], NOT the glyph. Output 90's
    `encoding_exists` / `reconstruction = F[F^-1[g]] = g` says exactly this;
    encoding the image directly reconstructs its transform instead.

    A random phase is imposed on the target amplitude first. Without it all
    the energy piles into DC, the hologram is nearly uniform, and the
    reconstruction is a single bright dot plus noise.
    """
    rng = np.random.default_rng(seed)
    t = np.asarray(target, dtype=float)
    ph = rng.uniform(0, 2 * np.pi, size=t.shape)
    return np.fft.ifft2(np.fft.ifftshift(t * np.exp(1j * ph)))


def gerchberg_saxton(target, iters=30, seed=0):
    """
    Iterative phase retrieval. Each round enforces the target amplitude in
    the reconstruction plane and unit amplitude in the hologram plane.
    Improves reconstruction fidelity substantially over one random-phase
    shot; 20-40 iterations is the usual plateau.
    """
    rng = np.random.default_rng(seed)
    t = np.asarray(target, dtype=float)
    t = t / t.max() if t.max() > 0 else t
    H = np.exp(1j * rng.uniform(0, 2 * np.pi, size=t.shape))
    for _ in range(iters):
        G = np.fft.fftshift(np.fft.fft2(H))
        G = t * np.exp(1j * np.angle(G))
        H = np.fft.ifft2(np.fft.ifftshift(G))
        H = np.exp(1j * np.angle(H))
    return H


def build_field(layers, focal_lengths, wavelength, dx, gs_iters=30, seed=0):
    """
    Stage 1: per-layer hologram, then axial placement by quadratic phase,
    then coherent sum. See ogr.fresnel for why the depth term is quadratic.
    """
    holograms = []
    for k, layer in enumerate(layers):
        if gs_iters and gs_iters > 0:
            holograms.append(gerchberg_saxton(layer, iters=gs_iters, seed=seed + k))
        else:
            holograms.append(hologram_from_target(layer, seed=seed + k))
    return fresnel.encode_layers(holograms, wavelength, dx, focal_lengths)


def build_pattern(field, f_c=0.125, axis="diag", stripe_width=3,
                  add_reference=True, shape=None):
    """
    Stages 2-4: Lee encode, overlay the diagonal reference, fit to the frame.

    The reference stripe is written as OFF mirrors (value 0) THROUGH the
    encoded hologram. It costs no extra hardware and it costs the hologram
    only the mirrors it occupies: stripe_width / min(ny, nx) of the aperture.
    """
    B = lee.encode_field(field, f_c=f_c, axis=axis)
    if add_reference:
        stripe = diagonal_stripe(B.shape, width=stripe_width)
        B = B.copy()
        B[stripe] = 0
    if shape is not None:
        B = fit_to_frame(B, shape)
    return B.astype(np.uint8)


def fit_to_frame(pattern, shape):
    """Centre-pad or centre-crop a pattern into the native DMD frame."""
    a = np.asarray(pattern)
    ny, nx = shape
    sy, sx = a.shape
    out = np.zeros((ny, nx), dtype=a.dtype)

    # crop the source where it is bigger, pad the destination where smaller,
    # independently per axis
    src_y0 = max(0, (sy - ny) // 2)
    src_x0 = max(0, (sx - nx) // 2)
    h = min(sy, ny)
    w = min(sx, nx)
    dst_y0 = max(0, (ny - sy) // 2)
    dst_x0 = max(0, (nx - sx) // 2)
    out[dst_y0:dst_y0 + h, dst_x0:dst_x0 + w] = a[src_y0:src_y0 + h,
                                                  src_x0:src_x0 + w]
    return out


def run(glyphs, outdir,
        focal_lengths=None,
        dmd=DLP4500,
        source=LED_RED,
        geometry=OGR_GEOMETRY,
        f_c=0.125,
        axis="diag",
        stripe_width=3,
        encode_size=1024,
        fill_fraction=None,
        gs_iters=30,
        seed=0,
        write_files=True):
    """
    Full pipeline. `glyphs` is a list of 2-D non-negative arrays (one per
    axial layer). Returns the manifest dict.
    """
    glyphs = [np.asarray(g, dtype=float) for g in glyphs]
    n = len(glyphs)
    if focal_lengths is None:
        focal_lengths = [np.inf] * n
    if len(focal_lengths) != n:
        raise ValueError("one focal length per glyph layer")

    # OFF-AXIS SIZING — measured, not guessed.
    # The DC (autocorrelation) term has half-width W where W is the glyph
    # half-width; the +1 order sits at f_c*N. Non-overlap needs
    #     f_c*N >= 1.5*W = 0.75*fill_fraction*N   ->   fill_fraction <= 1.33*f_c
    # Measured on a 1024 grid with f_c = 0.125:
    #     fill 0.500 -> reconstruction/target correlation -0.0003  FAIL
    #     fill 0.250 -> correlation -0.0003                        FAIL
    #     fill 0.125 -> correlation  0.9766                        PASS
    # Default therefore ties fill_fraction to f_c.
    if fill_fraction is None:
        fill_fraction = f_c
    if fill_fraction > 1.34 * f_c:
        raise ValueError(
            "fill_fraction %.3f exceeds 1.33*f_c = %.3f; the glyph will "
            "overlap the DC term and the reconstruction will be noise. "
            "Lower fill_fraction or raise f_c." % (fill_fraction, 1.33 * f_c))

    inner = max(int(encode_size * fill_fraction), 8)
    grid = []
    for g in glyphs:
        g = g / g.max() if g.max() > 0 else g
        small = _resize(g, (inner, inner))
        canvas = np.zeros((encode_size, encode_size), dtype=float)
        c0 = (encode_size - inner) // 2
        canvas[c0:c0 + inner, c0:c0 + inner] = small
        grid.append(canvas)

    dx = dmd.pitch
    field = build_field(grid, focal_lengths, source.wavelength, dx,
                        gs_iters=gs_iters, seed=seed)
    pattern = build_pattern(field, f_c=f_c, axis=axis,
                            stripe_width=stripe_width,
                            shape=(dmd.n_rows, dmd.n_cols))

    a_coh = dmd.aperture_short
    z = geometry.d_wall_recon
    manifest = {
        "package": "OGR_DMD_MathPackage",
        "version": "1.0",
        "device": dmd.name,
        "frame": [dmd.n_rows, dmd.n_cols],
        "source_nm": source.wavelength * 1e9,
        "carrier_cycles_per_mirror": f_c,
        "carrier_axis": axis,
        "reference_stripe_width_mirrors": stripe_width,
        "encode_grid": encode_size,
        "fill_fraction": fill_fraction,
        "glyph_pixels_in_grid": inner,
        "gerchberg_saxton_iters": gs_iters,
        "layers": n,
        "focal_lengths_m": [None if np.isinf(f) else float(f) for f in focal_lengths],
        "geometry": {
            "d_dmd_wall_m": geometry.d_dmd_wall,
            "d_wall_recon_m": geometry.d_wall_recon,
            "d_total_m": geometry.d_total,
        },
        "sampling": recon_report((dmd.n_rows, dmd.n_cols),
                                 source.wavelength, z, dmd.pitch),
        "resolution": {
            "coherent_aperture_m": a_coh,
            "numerical_aperture": fresnel.numerical_aperture(a_coh, z),
            "lateral_resolution_m": fresnel.lateral_resolution(source.wavelength, a_coh, z),
            "axial_resolution_m": fresnel.axial_resolution(source.wavelength, a_coh, z),
        },
        "glyph_lateral_offset_m": lee.glyph_offset_metres(
            f_c, source.wavelength, z, dmd.pitch),
        "first_order_intensity_efficiency": float(lee.first_order_efficiency(0.5)),
        "pattern_sequence": bmp.PATTERN_SEQUENCE_LIMITS,
        "on_fraction": float(pattern.mean()),
    }

    if write_files:
        os.makedirs(outdir, exist_ok=True)
        stem = os.path.join(outdir, "ogr_pattern_000")
        manifest["files"] = [os.path.basename(p)
                             for p in bmp.write_pattern(stem, pattern)]
        with open(os.path.join(outdir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
    manifest["_pattern"] = pattern
    return manifest


def simulate(pattern, crop=None):
    """
    Predicted intensity on the reconstruction plane. This is the number a
    bench photograph must be compared against — do not skip it.
    """
    img = intensity(reconstruct(np.asarray(pattern, dtype=float)))
    if crop:
        ny, nx = img.shape
        cy, cx = ny // 2, nx // 2
        r = crop // 2
        img = img[cy - r:cy + r, cx - r:cx + r]
    m = img.max()
    return img / m if m > 0 else img


def _resize(a, shape):
    """Nearest-neighbour resize; keeps the package dependency-light."""
    ny, nx = shape
    sy, sx = a.shape
    yi = (np.arange(ny) * sy // ny).clip(0, sy - 1)
    xi = (np.arange(nx) * sx // nx).clip(0, sx - 1)
    return a[yi][:, xi]


def text_glyph(char, size=512, thickness=None):
    """
    A dependency-free block glyph for smoke-testing: draws a filled shape
    keyed to `char` so the pipeline can run with no image assets.
    Supported: 'X', 'O', 'L', 'T', '+', 'square', 'tri'.
    """
    a = np.zeros((size, size), dtype=float)
    t = thickness or max(size // 12, 3)
    i, j = np.indices((size, size))
    c = size // 2
    if char == "X":
        a[(np.abs(i - j) < t) | (np.abs(i + j - size) < t)] = 1.0
    elif char == "O":
        r = np.hypot(i - c, j - c)
        a[(r < size * 0.38) & (r > size * 0.38 - t)] = 1.0
    elif char == "L":
        a[(j < t + size // 6) & (i > size // 6)] = 1.0
        a[(i > size - t - size // 6) & (j < size - size // 6)] = 1.0
    elif char == "T":
        a[(i < t + size // 6) & (j > size // 6) & (j < size - size // 6)] = 1.0
        a[(np.abs(j - c) < t) & (i < size - size // 6)] = 1.0
    elif char == "+":
        a[(np.abs(i - c) < t) | (np.abs(j - c) < t)] = 1.0
        a[(np.abs(i - c) > size // 3) | (np.abs(j - c) > size // 3)] = 0.0
    elif char == "square":
        a[(np.abs(i - c) < size // 4) & (np.abs(j - c) < size // 4)] = 1.0
    elif char == "tri":
        a[(i > c - size // 4) & (i < c + size // 4) &
          (np.abs(j - c) < (i - (c - size // 4)))] = 1.0
    else:
        raise ValueError("unsupported glyph key: %r" % char)
    return a
