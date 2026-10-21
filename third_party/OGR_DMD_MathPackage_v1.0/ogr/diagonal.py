"""
ogr.diagonal — the built-in 45-degree zero-line depth reference.

CLAIM (output 91 Claim C): a diagonal stripe of OFF mirrors on the DLP4500
produces, in the reconstruction plane, a bright LINE PERPENDICULAR to the
stripe. That line is the z = 0 reference marker. No beam splitter, no
reference arm, no second source.

ORIENTATION — corrected here, and this correction is load-bearing
--------------------------------------------------------------------------
A stripe running ALONG unit direction d is constant along d and narrow
along its normal n (with <d, n> = 0). It is separable:

    A(x) = g(<x, n>) * 1(<x, d>)

so  F[A](w) = G(<w, n>) * delta(<w, d>)

i.e. the transform is supported on { w : <d, w> = 0 } = span{n}.

  * stripe along DiagDir = (1, 1)  ->  reconstruction line along (1, -1)
  * the defining functional is <DiagDir, w>, NOT <PerpDir, w>

Output 93 defined ReferenceLine via <DiagDir, .> but PosDepth/NegDepth via
<PerpDir, .>. Those are two different functionals, so the three sets are not
a partition — which is exactly why Aristotle rejected `depth_trichotomy`.
Output 94 repaired consistency by moving ALL THREE to <PerpDir, .>. That is
internally consistent but flips the physics: it makes the reference line
span{(1,1)}, parallel to the stripe, which the transform does not do.

CORRECT REPAIR (use this in the Lean patch, see docs/LEAN_PATCH.md):
    ReferenceLine := { w | <DiagDir, w> = 0 }
    PosDepth      := { w | <DiagDir, w> > 0 }
    NegDepth      := { w | <DiagDir, w> < 0 }
One functional, three regions, partition holds, physics holds.
`test_diagonal.py` pins this empirically with an FFT, so the convention is
not a matter of taste.
"""

import numpy as np

from .fourier import reconstruct, intensity

DIAG_DIR = np.array([1.0, 1.0]) / np.sqrt(2.0)   # stripe runs along this
PERP_DIR = np.array([1.0, -1.0]) / np.sqrt(2.0)  # transform line lies along this


def diagonal_stripe(shape, width=1, offset=0, anti=False):
    """
    Boolean mask of a 45-degree stripe.

    anti=False : stripe runs along (1, 1)   -> mask on |(j - i) - offset| <= w/2
    anti=True  : stripe runs along (1, -1)  -> mask on |(i + j) - offset| <= w/2

    Note the index convention: i is the row (y, downward), j the column (x).
    With y downward, constant (j - i) traces the (1, 1) direction in (x, y).
    """
    ny, nx = shape
    i, j = np.indices((ny, nx))
    if anti:
        s = (i + j) - (offset + (ny + nx) // 2)
    else:
        s = (j - i) - offset
    return np.abs(s) <= width / 2.0


def reference_line_functional(shape, direction=DIAG_DIR):
    """
    <direction, w> sampled on the reconstruction grid, DC-centred.
    Sign of this array gives the depth trichotomy regions.
    """
    ny, nx = shape
    wy, wx = np.indices((ny, nx))
    wx = wx - nx // 2
    wy = wy - ny // 2
    return direction[0] * wx + direction[1] * wy


def depth_trichotomy(shape, direction=DIAG_DIR, tol=0.5):
    """
    [PROVED] Partition of the reconstruction plane into
      reference (|<d,w>| <= tol), positive depth, negative depth.
    Returns three boolean masks whose union is everything and whose
    pairwise intersections are empty.
    """
    f = reference_line_functional(shape, direction)
    ref = np.abs(f) <= tol
    pos = f > tol
    neg = f < -tol
    return ref, pos, neg


def trichotomy_is_partition(shape, direction=DIAG_DIR, tol=0.5):
    """[PROVED-numeric] union == all, pairwise intersections empty."""
    ref, pos, neg = depth_trichotomy(shape, direction, tol)
    union_all = bool(np.all(ref | pos | neg))
    disjoint = bool(
        not np.any(ref & pos) and not np.any(ref & neg) and not np.any(pos & neg)
    )
    return union_all and disjoint


def measure_line_direction(pattern):
    """
    Empirically recover the direction of the transform's energy line by the
    principal axis of the intensity-weighted second-moment matrix.
    Returns a unit vector (vx, vy) in reconstruction-plane coordinates.
    """
    img = intensity(reconstruct(pattern))
    ny, nx = img.shape
    yy, xx = np.indices((ny, nx))
    xx = (xx - nx // 2).astype(float)
    yy = (yy - ny // 2).astype(float)
    w = img.copy()
    w[ny // 2, nx // 2] = 0.0          # drop DC, it is isotropic
    tot = w.sum()
    if tot == 0:
        return np.array([0.0, 0.0])
    sxx = float((w * xx * xx).sum() / tot)
    syy = float((w * yy * yy).sum() / tot)
    sxy = float((w * xx * yy).sum() / tot)
    m = np.array([[sxx, sxy], [sxy, syy]])
    vals, vecs = np.linalg.eigh(m)
    v = vecs[:, int(np.argmax(vals))]
    if v[0] < 0:
        v = -v
    return v


# ---------------------------------------------------------------------------
# Diamond lattice
# ---------------------------------------------------------------------------

def diamond_positions(shape, pitch):
    """
    [ASSERTED — VERIFY ON HARDWARE] Physical mirror centres for the DLP4500
    diamond array, modelled as a centred-rectangular lattice: odd rows are
    displaced by half a pitch in x, rows spaced by pitch/2 in y.

    This is the standard reading of TI's "diamond pixel" description, but the
    package does NOT treat it as established. The observable that settles it
    is the projected diffraction-order pattern: an orthogonal lattice gives
    orders on a square grid aligned to the array axes; the centred-rectangular
    lattice gives orders on a grid rotated 45 degrees with half-order
    extinctions. Photograph the order pattern and compare before trusting any
    absolute order position computed from this function.
    """
    ny, nx = shape
    i, j = np.indices((ny, nx))
    x = (j + 0.5 * (i % 2)) * pitch
    y = i * (pitch / 2.0)
    return x, y


def smooth_axis_note():
    return (
        "DLP4500 diamond lattice -> smooth axis at 45 deg; a 45-deg stripe is "
        "quantisation-free, an H or V stripe is jagged at half-pitch. "
        "DLP3010 orthogonal lattice -> smooth axis at 0 deg; horizontal fringes "
        "are clean, which is why it is the reference-beam device in the "
        "two-DMD architecture (output 94)."
    )
