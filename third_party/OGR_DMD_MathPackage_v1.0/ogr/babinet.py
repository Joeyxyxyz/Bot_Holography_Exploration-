"""
ogr.babinet — Babinet complementarity of ON and OFF mirrors.

[PROVED] (output 91 `babinet_identity`, output 93 `babinet93`)

    F[t_ON] + F[t_OFF] = F[t_full]

For a binary DMD, t_OFF = 1 - t_ON pointwise, so t_ON + t_OFF = 1 and
F[1] = N_total * delta(f). Numerically the sum is N_total at DC and
exactly zero elsewhere (to float round-off).

[HEURISTIC] MNF reading (output 91 `babinet_is_nullification`):
    N + R = identity   <->   F[ON] + F[OFF] = F[full]
    ON  mirrors  -> N branch (glyph content)
    OFF mirrors  -> R branch (reservoir / depth reference)

CAVEAT, stated plainly: physical Babinet for a DMD is exact only for the
FIELD leaving the array. The OFF mirrors send light to the dump, so on the
wall you observe |F[ON]|^2 alone; the complementary field is present as a
mathematical object, not as measurable intensity in the same direction.
The reference-line-for-free claim survives because the reference stripe is
built from mirrors you were going to leave OFF anyway inside the ON pattern
support — not because the dumped light reappears.
"""

import numpy as np

from .fourier import reconstruct


def complement(pattern):
    """[PROVED] Binary Babinet complement, t_OFF = 1 - t_ON."""
    a = np.asarray(pattern)
    return 1.0 - a


def are_complementary(a_on, a_off, tol=1e-12):
    """[PROVED] Check A_on + A_off = A_full (all ones)."""
    s = np.asarray(a_on) + np.asarray(a_off)
    return bool(np.max(np.abs(s - 1.0)) <= tol)


def babinet_residual(pattern):
    """
    [PROVED-numeric] Max deviation of F[ON] + F[OFF] from F[full].
    Kill criterion: residual / N_total < 1e-12.
    """
    a = np.asarray(pattern, dtype=float)
    lhs = reconstruct(a) + reconstruct(complement(a))
    rhs = reconstruct(np.ones_like(a))
    return float(np.max(np.abs(lhs - rhs)))


def conservation_check(pattern):
    """
    Full N + R = identity report for one pattern.
    Returns a dict; `passes` is the gate.
    """
    a = np.asarray(pattern, dtype=float)
    n_total = a.size
    resid = babinet_residual(a)
    full = reconstruct(np.ones_like(a))
    dc = np.abs(full[a.shape[0] // 2, a.shape[1] // 2])
    off_dc = np.abs(full).copy()
    off_dc[a.shape[0] // 2, a.shape[1] // 2] = 0.0
    return {
        "n_total": n_total,
        "F_full_dc": float(dc),
        "F_full_max_offdc": float(off_dc.max()),
        "babinet_residual": resid,
        "normalised_residual": resid / n_total,
        "passes": resid / n_total < 1e-12,
    }
