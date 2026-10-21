"""
ogr.signed_depth — the +/-0.0e mirror-group construction (outputs 87, 88, 92)
rendered as executable geometry, plus PWM pool accumulation.

MIRROR GROUPS
    M+  : upper-left triangle   (j - i >  w/2)   -> +0.0e, positive layer
    M-  : lower-right triangle  (j - i < -w/2)   -> -0.0e, negative layer
    M0  : diagonal band         (|j - i| <= w/2) -> [0] ground, z = 0 marker

[PROVED] The three groups partition the array and are pairwise disjoint, so
no mirror is simultaneously +0.0e and -0.0e. That is the whole content of
output 87's `configs_disjoint` / `signed_separation` at the array level: it
is a set-theoretic fact about the partition, not a physical claim. Stated
that way it is true and cheap. Do not let it be quoted as evidence that the
two depth LAYERS cannot interfere — that is a different, stronger claim and
it needs the axial-resolution argument in ogr.fresnel, not this partition.

POOL ACCUMULATION (output 88, Nullification Geometry Workbook)
    Three sub-threshold contributions, each individually [0.0e], sum past
    the threshold to give an observable [1]:
        0.4 + 0.4 + 0.4 = 1.2 >= 1.0  with each 0.4 < 1.0
    On the DMD this is PWM duty pooled over frames. The physical caveat is
    that pooling is INTENSITY addition over time (incoherent), so it works
    for brightness but does not by itself create coherent structure. Use it
    to reach visibility, not to synthesise a field.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Signed classification (outputs 56/57/87), on the reals
# ---------------------------------------------------------------------------

GROUND = "ground"           # [0]
POS_RESERVOIR = "pos_0e"    # [+0.0e]
NEG_RESERVOIR = "neg_0e"    # [-0.0e]
OBSERVABLE = "observable"   # [1]


def signed_classify(x, delta):
    """
    [PROVED] Four-class signed classification.
      x == 0            -> ground
      0 < |x| < delta   -> pos/neg reservoir by sign of x
      |x| >= delta      -> observable
    """
    if x == 0:
        return GROUND
    if abs(x) < delta:
        return POS_RESERVOIR if x > 0 else NEG_RESERVOIR
    return OBSERVABLE


def N_op(x, delta):
    """[PROVED] Nullification operator: keeps only observable content."""
    return x if abs(x) >= delta else 0.0


def R_op(x, delta):
    """[PROVED] Remainder operator. Conservation: N + R = id."""
    return x - N_op(x, delta)


def conservation_holds(xs, delta, tol=1e-15):
    """[PROVED-numeric] N(x) + R(x) = x for every sample."""
    return all(abs(N_op(x, delta) + R_op(x, delta) - x) <= tol for x in xs)


# ---------------------------------------------------------------------------
# Mirror-group geometry
# ---------------------------------------------------------------------------

def mirror_groups(shape, band_width=1, offset=0):
    """
    [PROVED] Partition of the array into (M_pos, M_neg, M_ground) by the
    diagonal band. Returns three boolean masks.
    """
    ny, nx = shape
    i, j = np.indices((ny, nx))
    s = (j - i) - offset
    ground = np.abs(s) <= band_width / 2.0
    pos = s > band_width / 2.0
    neg = s < -band_width / 2.0
    return pos, neg, ground


def groups_partition(shape, band_width=1, offset=0):
    """[PROVED-numeric] union is everything, pairwise intersections empty."""
    pos, neg, ground = mirror_groups(shape, band_width, offset)
    return (
        bool(np.all(pos | neg | ground))
        and not bool(np.any(pos & neg))
        and not bool(np.any(pos & ground))
        and not bool(np.any(neg & ground))
    )


def group_counts(shape, band_width=1, offset=0):
    pos, neg, ground = mirror_groups(shape, band_width, offset)
    return {
        "pos": int(pos.sum()),
        "neg": int(neg.sum()),
        "ground": int(ground.sum()),
        "total": int(np.prod(shape)),
    }


# ---------------------------------------------------------------------------
# PWM pool accumulation
# ---------------------------------------------------------------------------

def pool(contributions):
    """[PROVED] Sum of contributions."""
    return float(np.sum(contributions))


def pool_crosses(contributions, delta):
    """
    [PROVED] Each contribution individually sub-threshold, pool observable.
    Returns (each_below, pool_value, crosses).
    """
    each_below = all(abs(c) < delta for c in contributions)
    p = pool(contributions)
    return each_below, p, abs(p) >= delta


def frames_needed(duty, delta):
    """
    [PROVED] Minimum frame count n with n * duty >= delta, duty < delta.
    Raises if duty is already observable (no pooling required).
    """
    if duty <= 0:
        raise ValueError("duty must be positive")
    if duty >= delta:
        raise ValueError("duty already crosses threshold; pooling is trivial")
    return int(np.ceil(delta / duty))


def pool_time(duty, delta, frame_rate_hz):
    """Wall-clock time to accumulate an observable pool, seconds."""
    return frames_needed(duty, delta) / frame_rate_hz


def flicker_ok(duty, delta, frame_rate_hz, fusion_hz=60.0):
    """
    [ASSERTED] The pooled result is perceived as steady only if the whole
    pool completes faster than the flicker-fusion period. Kill criterion for
    any "invisible parts pool to a visible whole" demonstration that is meant
    to be seen by eye rather than by a camera with a long exposure.
    """
    return pool_time(duty, delta, frame_rate_hz) <= 1.0 / fusion_hz
