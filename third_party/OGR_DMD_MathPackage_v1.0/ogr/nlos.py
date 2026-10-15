"""
ogr.nlos — non-line-of-sight projection as the formal dual of NLoS
reconstruction (output 89).

    H   : wall illumination -> hidden-scene field
    H^-1: hidden-scene field -> wall illumination

    reconstruction:  psi measured, solve  phi = H^-1 psi
    projection:      psi chosen,   solve  phi = H^-1 psi

Same operator, same inversion, opposite direction of intent.
[PROVED] Hadamard case: H_n H_n^T = 2^n I, so H^-1 = H^T / 2^n.

HONEST STATUS OF THE DUALITY
--------------------------------------------------------------------------
The algebra is exact. The physics is not symmetric, and the package says so:

  * H is a Lambertian scattering kernel. It is severely ill-conditioned:
    the singular values fall off fast, so H^-1 amplifies noise and demands
    dynamic range the DMD does not have. `condition_report` measures this
    for your actual geometry — run it before believing any projection result.
  * phi must be NON-NEGATIVE and bounded (a DMD emits light, it cannot
    subtract). H^-1 psi is signed in general. A physical solution requires a
    constrained solve (non-negative least squares), which is what
    `solve_nonneg` does, not a raw inverse.
  * Reconstruction gets to average many measurements. Projection gets one
    shot per frame. The error budgets are not comparable.

None of this kills the idea. It says the deliverable is a conditioning
number and a constrained solve, not an inverse.
"""

import numpy as np


def hadamard(n):
    """
    [PROVED] Sylvester Hadamard matrix of order 2^n.
    H_n H_n^T = 2^n I.
    """
    H = np.array([[1.0]])
    for _ in range(n):
        H = np.block([[H, H], [H, -H]])
    return H


def hadamard_orthogonality_residual(n):
    """[PROVED-numeric] max |H H^T - 2^n I|. Kill criterion: < 1e-9."""
    H = hadamard(n)
    return float(np.max(np.abs(H @ H.T - (2 ** n) * np.eye(2 ** n))))


def hadamard_inverse(n):
    """[PROVED] H^-1 = H^T / 2^n."""
    return hadamard(n).T / (2 ** n)


def lambertian_kernel(wall_pts, scene_pts, albedo=0.85,
                      wall_normal=(0.0, 0.0, 1.0),
                      scene_normal=(0.0, 0.0, -1.0)):
    """
    [ASSERTED] Lambertian transport matrix
        H[s, w] = rho * cos(theta_i) * cos(theta_o) / (pi * r^2)
    wall_pts  : (Nw, 3) array of relay-wall sample positions
    scene_pts : (Ns, 3) array of hidden-scene sample positions
    returns   : (Ns, Nw) matrix
    """
    W = np.asarray(wall_pts, dtype=float)
    S = np.asarray(scene_pts, dtype=float)
    nw = np.asarray(wall_normal, dtype=float)
    ns = np.asarray(scene_normal, dtype=float)
    nw = nw / np.linalg.norm(nw)
    ns = ns / np.linalg.norm(ns)

    d = S[:, None, :] - W[None, :, :]            # (Ns, Nw, 3)
    r = np.linalg.norm(d, axis=2)
    r = np.maximum(r, 1e-9)
    u = d / r[:, :, None]
    cos_o = np.abs(u @ nw)
    cos_i = np.abs((-u) @ ns)
    return albedo * cos_i * cos_o / (np.pi * r ** 2)


def condition_report(H, rank_tol=1e-10):
    """
    Singular-value diagnosis of the transport operator. Everything downstream
    of an inverse depends on these numbers.
    """
    s = np.linalg.svd(H, compute_uv=False)
    s_max = float(s[0])
    s_min = float(s[-1])
    rank = int(np.sum(s > rank_tol * s_max))
    return {
        "shape": H.shape,
        "sigma_max": s_max,
        "sigma_min": s_min,
        "condition_number": float(s_max / max(s_min, 1e-300)),
        "numerical_rank": rank,
        "rank_deficiency": int(min(H.shape) - rank),
        "dynamic_range_bits_needed": float(np.log2(max(s_max / max(s_min, 1e-300), 1.0))),
        "dmd_bits_available": 8.0,
        "feasible_unregularised": bool(np.log2(max(s_max / max(s_min, 1e-300), 1.0)) <= 8.0),
    }


def solve_tikhonov(H, psi, lam=1e-3):
    """Regularised inverse: argmin ||H phi - psi||^2 + lam ||phi||^2."""
    H = np.asarray(H, dtype=float)
    A = H.T @ H + lam * np.eye(H.shape[1])
    return np.linalg.solve(A, H.T @ np.asarray(psi, dtype=float))


def solve_nonneg(H, psi, iters=500, lam=1e-6):
    """
    Physically admissible solve: multiplicative updates keeping phi >= 0,
    which is what a light-emitting device can actually display.
    """
    H = np.asarray(H, dtype=float)
    psi = np.asarray(psi, dtype=float)
    phi = np.ones(H.shape[1]) * (psi.mean() / max(H.mean(), 1e-12) / H.shape[1])
    phi = np.maximum(phi, 1e-12)
    Ht1 = H.T @ np.ones_like(psi)
    for _ in range(iters):
        est = H @ phi
        est = np.maximum(est, 1e-12)
        phi = phi * (H.T @ (psi / est)) / np.maximum(Ht1 + lam, 1e-12)
        phi = np.maximum(phi, 0.0)
    return phi


def duality_residual(H, psi_desired, lam=1e-3):
    """
    Round-trip test of the duality claim: choose psi, invert to phi,
    forward-propagate, compare. Returns relative error.
    """
    phi = solve_tikhonov(H, psi_desired, lam)
    back = np.asarray(H) @ phi
    denom = np.linalg.norm(psi_desired)
    return float(np.linalg.norm(back - psi_desired) / max(denom, 1e-30))
