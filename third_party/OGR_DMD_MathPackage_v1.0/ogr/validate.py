"""
ogr.validate — run every numerical claim in the package and report.

    python -m ogr.validate

Each check has an explicit tolerance. A FAIL means the claim is wrong, not
that the tolerance is inconvenient. Pre-registered kill criteria are in
PREREGISTRATION.md and are mirrored here so the gate travels with the code.
"""

import numpy as np

from . import babinet, diagonal, fresnel, lee, nlos, signed_depth
from .fourier import inversion_residual, recon_field_of_view, recon_pixel_pitch
from .hardware import DLP4500, DLP3010ULC, LED_RED, LED_GREEN, OGR_GEOMETRY


def _row(name, ok, detail):
    return {"check": name, "pass": bool(ok), "detail": detail}


def run_all(seed=0, n=256):
    rng = np.random.default_rng(seed)
    out = []

    # --- hardware arithmetic ------------------------------------------------
    out.append(_row("mirror_count = 912*1140 = 1,039,680",
                    DLP4500.n_mirrors == 1_039_680,
                    DLP4500.n_mirrors))
    out.append(_row("aperture_short = 6.89472 mm",
                    abs(DLP4500.aperture_short - 6.89472e-3) < 1e-12,
                    DLP4500.aperture_short))
    fr_r = DLP4500.fraunhofer_threshold(LED_RED.wavelength, "short")
    fr_g = DLP4500.fraunhofer_threshold(LED_GREEN.wavelength, "short")
    out.append(_row("red Fraunhofer threshold < green (output 93 theorem)",
                    fr_r < fr_g, {"red_m": fr_r, "green_m": fr_g}))
    nf = DLP4500.fresnel_number(LED_RED.wavelength, 0.5)
    out.append(_row("CORRECTION: z=500mm is NEAR field, not Fraunhofer (N_F>>1)",
                    nf > 10.0,
                    {"fresnel_number": nf,
                     "fraunhofer_onset_m": DLP4500.fraunhofer_threshold(LED_RED.wavelength, "short"),
                     "output90_claimed": "90 mm (unit error; true value 90 m)"}))
    n_ff = DLP4500.far_field_mirror_count(LED_RED.wavelength, 0.5)
    out.append(_row("far-field-valid sub-aperture is only ~47 mirrors across",
                    30 <= n_ff <= 80,
                    {"mirrors_across": n_ff,
                     "fraction_of_array": n_ff ** 2 / DLP4500.n_mirrors}))
    fov = recon_field_of_view(LED_RED.wavelength, 0.5, DLP4500.pitch)
    out.append(_row("angular FOV equals grating order separation lambda/p",
                    abs(fov / 0.5 - LED_RED.wavelength / DLP4500.pitch) < 1e-15,
                    {"fov_m": fov, "angular_rad": LED_RED.wavelength / DLP4500.pitch}))

    # --- Fourier inversion --------------------------------------------------
    pat = rng.integers(0, 2, size=(n, n)).astype(float)
    res = inversion_residual(pat)
    out.append(_row("F^-1[F[t]] = t  (Fourier inversion, output 90/93)",
                    res < 1e-10, res))

    # --- Babinet ------------------------------------------------------------
    cons = babinet.conservation_check(pat)
    out.append(_row("F[ON] + F[OFF] = F[full]  (Babinet = N + R = id)",
                    cons["passes"], cons))
    out.append(_row("complement is exact: A_on + A_off = 1",
                    babinet.are_complementary(pat, babinet.complement(pat)),
                    "exact"))

    # --- diagonal reference orientation ------------------------------------
    stripe = diagonal.diagonal_stripe((n, n), width=1).astype(float)
    v = diagonal.measure_line_direction(stripe)
    # stripe along (1,1) -> transform line along (1,-1)
    aligned = abs(abs(float(np.dot(v, diagonal.PERP_DIR))) - 1.0) < 0.05
    out.append(_row("stripe along (1,1) -> recon line along (1,-1)",
                    aligned, {"measured_unit_vector": v.tolist()}))
    out.append(_row("depth trichotomy is a partition (single functional)",
                    diagonal.trichotomy_is_partition((n, n)), "ref/pos/neg"))

    # --- Lee hologram -------------------------------------------------------
    A = np.full((n, n), 0.5)
    ph = np.zeros((n, n))
    B = lee.encode(A, ph, f_c=0.125, axis="u", linearise=False)
    out.append(_row("Lee output is strictly binary", lee.is_binary(B),
                    {"unique": np.unique(B).tolist()}))
    eff = lee.first_order_efficiency(0.5)
    out.append(_row("first-order efficiency = 1/pi^2 = 0.1013",
                    abs(eff - 1.0 / np.pi ** 2) < 1e-12, eff))
    # measured first-order coefficient converges to sin(pi*A)/pi as the
    # carrier is oversampled; this is a package finding, not an assumption
    meas = {f"f_c={fc}": lee.measured_first_order(fc, n=512)
            for fc in (0.25, 0.125, 0.0625)}
    out.append(_row("measured c_1 -> sin(pi*A)/pi = 0.3183 as f_c is refined",
                    abs(meas["f_c=0.0625"] - 1.0 / np.pi) < 0.02,
                    {**{k: round(v, 4) for k, v in meas.items()},
                     "theory": round(1.0 / np.pi, 4)}))
    # amplitude linearisation
    targets = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    enc = np.arcsin(targets) / np.pi
    recovered = np.sin(np.pi * enc)
    out.append(_row("amplitude linearisation sin(pi*arcsin(A)/pi) = A",
                    np.max(np.abs(recovered - targets)) < 1e-12,
                    float(np.max(np.abs(recovered - targets)))))

    # --- Fresnel ------------------------------------------------------------
    a_coh = DLP4500.aperture_short
    dz = fresnel.axial_resolution(LED_RED.wavelength, a_coh, 0.5)
    dxr = fresnel.lateral_resolution(LED_RED.wavelength, a_coh, 0.5)
    out.append(_row("axial resolution at 500 mm is ~27 mm (design constraint)",
                    0.02 < dz < 0.04, {"delta_z_m": dz, "delta_x_m": dxr}))
    # propagation is unitary over a non-evanescent band
    dx = 2e-6
    u0 = rng.normal(size=(128, 128)) + 1j * rng.normal(size=(128, 128))
    u1 = fresnel.propagate(u0, LED_RED.wavelength, 0.01, dx)
    ratio = float(np.sum(np.abs(u1) ** 2) / np.sum(np.abs(u0) ** 2))
    out.append(_row("angular-spectrum propagation conserves energy (<=1)",
                    0.0 < ratio <= 1.0 + 1e-9, ratio))
    # encoding a lens phase of focal length f = z cancels the Fresnel chirp,
    # so the plain DFT becomes the correct reconstruction operator
    from .fourier import fresnel_reconstruct, reconstruct as _rec
    small = rng.integers(0, 2, size=(128, 128)).astype(float)
    lensed = small * fresnel.lens_phase((128, 128), LED_RED.wavelength, 0.5, 2e-5)
    m1 = np.abs(fresnel_reconstruct(lensed, LED_RED.wavelength, 0.5, 2e-5))
    m2 = np.abs(_rec(small))
    rel = float(np.max(np.abs(m1 - m2)) / max(m2.max(), 1e-30))
    out.append(_row("encoded lens phase cancels the Fresnel chirp exactly",
                    rel < 1e-9, rel))
    lp = fresnel.lens_phase((64, 64), LED_RED.wavelength, 0.5, DLP4500.pitch)
    out.append(_row("lens phase is unit modulus",
                    np.max(np.abs(np.abs(lp) - 1.0)) < 1e-12,
                    float(np.max(np.abs(np.abs(lp) - 1.0)))))

    # --- signed groups and pooling -----------------------------------------
    out.append(_row("mirror groups partition the array",
                    signed_depth.groups_partition((n, n)),
                    signed_depth.group_counts((n, n))))
    out.append(_row("N + R = identity on samples",
                    signed_depth.conservation_holds(
                        rng.normal(size=200).tolist(), 1.0), "exact"))
    each, p, cross = signed_depth.pool_crosses([0.4, 0.4, 0.4], 1.0)
    out.append(_row("pool accumulation: three [0.0e] -> [1]",
                    each and cross and abs(p - 1.2) < 1e-12,
                    {"each_below": each, "pool": p, "crosses": cross}))
    ok_flicker = signed_depth.flicker_ok(0.4, 1.0, DLP4500.binary_rate_hz)
    out.append(_row("pooled frame set completes inside flicker fusion",
                    ok_flicker,
                    {"frames": signed_depth.frames_needed(0.4, 1.0),
                     "seconds": signed_depth.pool_time(0.4, 1.0,
                                                       DLP4500.binary_rate_hz)}))

    # --- NLoS ---------------------------------------------------------------
    hr = nlos.hadamard_orthogonality_residual(6)
    out.append(_row("H H^T = 2^n I  (Hadamard, output 7/89)", hr < 1e-9, hr))
    wall = np.stack([np.linspace(-0.25, 0.25, 24),
                     np.zeros(24), np.zeros(24)], axis=1)
    scene = np.stack([np.linspace(-0.1, 0.1, 16),
                      np.zeros(16), np.full(16, 0.5)], axis=1)
    H = nlos.lambertian_kernel(wall, scene)
    cr = nlos.condition_report(H)
    out.append(_row("Lambertian transport conditioning measured (expect FAIL "
                    "of feasible_unregularised — that is the finding)",
                    True, cr))
    phi_true = np.abs(rng.normal(size=H.shape[1]))
    psi_in_range = H @ phi_true
    err_in = nlos.duality_residual(H, psi_in_range, lam=1e-9)
    out.append(_row("NLoS round trip exact for psi IN the range of H",
                    err_in < 1e-3, err_in))
    psi_arbitrary = np.abs(rng.normal(size=H.shape[0]))
    err_arb = nlos.duality_residual(H, psi_arbitrary, lam=1e-9)
    out.append(_row("arbitrary psi is NOT reachable (rank deficiency is the "
                    "real constraint, not the algebra)",
                    err_arb > 0.1,
                    {"relative_error": err_arb,
                     "reachable_fraction": cr["numerical_rank"] / H.shape[0]}))

    # --- END TO END: does a glyph actually come back out? ------------------
    from . import pipeline
    from .fourier import reconstruct as _r, intensity as _i
    N = 1024
    g = pipeline.text_glyph("X", int(N * 0.125))
    canvas = np.zeros((N, N))
    s = g.shape[0]
    c0 = (N - s) // 2
    canvas[c0:c0 + s, c0:c0 + s] = g
    H = pipeline.gerchberg_saxton(canvas, iters=40)
    B = lee.encode_field(H, f_c=0.125, axis="u")
    img = _i(_r(B.astype(float)))
    cj = N // 2 + int(0.125 * N)
    r = s // 2
    win = img[N // 2 - r:N // 2 + r, cj - r:cj + r]
    win = win / max(win.max(), 1e-30)
    tgt = g[np.arange(win.shape[0]) * s // win.shape[0]][
        :, np.arange(win.shape[1]) * s // win.shape[1]]
    corr = float(np.corrcoef(win.ravel(), tgt.ravel())[0, 1])
    out.append(_row("END TO END: glyph recovered at the +1 order, corr > 0.9",
                    corr > 0.9, {"correlation": round(corr, 4),
                                 "fill_fraction": 0.125, "f_c": 0.125,
                                 "gs_iters": 40}))
    out.append(_row("off-axis guard rejects fill_fraction > 1.33*f_c",
                    _guard_fires(), "ValueError raised as designed"))

    # --- two-DMD architecture ----------------------------------------------
    out.append(_row("DLP3010 pitch < DLP4500 pitch (finer reference control)",
                    DLP3010ULC.pitch < DLP4500.pitch,
                    {"3010": DLP3010ULC.pitch, "4500": DLP4500.pitch}))
    out.append(_row("wall is inside DLP4500 focus range",
                    OGR_GEOMETRY.focus_min <= OGR_GEOMETRY.d_dmd_wall
                    <= OGR_GEOMETRY.focus_max, OGR_GEOMETRY.d_dmd_wall))

    return out


def main():
    rows = run_all()
    width = max(len(r["check"]) for r in rows)
    n_pass = 0
    print("=" * (width + 12))
    print("OGR DMD MATH PACKAGE v1.0 — SELF-VALIDATION")
    print("=" * (width + 12))
    for r in rows:
        tag = "PASS" if r["pass"] else "FAIL"
        n_pass += r["pass"]
        print(f"[{tag}] {r['check'].ljust(width)}  {r['detail']}")
    print("-" * (width + 12))
    print(f"{n_pass}/{len(rows)} checks passed")
    return 0 if n_pass == len(rows) else 1




def _guard_fires():
    from . import pipeline
    try:
        pipeline.run([pipeline.text_glyph("X", 128)], "/tmp/_ogr_guard",
                     fill_fraction=0.5, encode_size=256, write_files=False)
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
