"""
Standalone + pytest-compatible test suite.

    python3 tests/test_all.py      (no pytest needed)
    pytest tests/                  (if pytest is available)

Every assertion mirrors a pre-registered kill criterion. Do not relax a
tolerance to make a test pass.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ogr import validate, babinet, diagonal, lee, fresnel, nlos, signed_depth, bmp, pipeline
from ogr.fourier import inversion_residual
from ogr.hardware import DLP4500, LED_RED


def test_full_validation_suite():
    rows = validate.run_all()
    failed = [r["check"] for r in rows if not r["pass"]]
    assert not failed, "failed checks: %s" % failed


def test_mirror_count():
    assert DLP4500.n_mirrors == 1_039_680


def test_near_field_correction():
    assert DLP4500.fresnel_number(LED_RED.wavelength, 0.5) > 10.0
    assert not DLP4500.is_far_field(LED_RED.wavelength, 0.5)


def test_fourier_inversion():
    rng = np.random.default_rng(1)
    p = rng.integers(0, 2, size=(128, 128)).astype(float)
    assert inversion_residual(p) < 1e-10


def test_babinet_conservation():
    rng = np.random.default_rng(2)
    p = rng.integers(0, 2, size=(128, 128)).astype(float)
    assert babinet.conservation_check(p)["passes"]


def test_reference_line_orientation():
    s = diagonal.diagonal_stripe((256, 256), width=1).astype(float)
    v = diagonal.measure_line_direction(s)
    assert abs(abs(float(np.dot(v, diagonal.PERP_DIR))) - 1.0) < 0.05


def test_trichotomy_partition():
    assert diagonal.trichotomy_is_partition((128, 128))


def test_lee_binary_and_efficiency():
    A = np.full((64, 64), 0.5)
    B = lee.encode(A, np.zeros((64, 64)), f_c=0.125)
    assert lee.is_binary(B)
    assert abs(lee.first_order_efficiency(0.5) - 1.0 / np.pi ** 2) < 1e-12


def test_carrier_sampling_converges():
    coarse = lee.measured_first_order(0.25, n=512)
    fine = lee.measured_first_order(0.03125, n=512)
    assert abs(fine - 1 / np.pi) < abs(coarse - 1 / np.pi)
    assert abs(fine - 1 / np.pi) < 0.01


def test_lens_phase_cancels_chirp():
    from ogr.fourier import fresnel_reconstruct, reconstruct
    rng = np.random.default_rng(3)
    a = rng.integers(0, 2, size=(128, 128)).astype(float)
    lensed = a * fresnel.lens_phase((128, 128), LED_RED.wavelength, 0.5, 2e-5)
    m1 = np.abs(fresnel_reconstruct(lensed, LED_RED.wavelength, 0.5, 2e-5))
    m2 = np.abs(reconstruct(a))
    assert np.max(np.abs(m1 - m2)) / m2.max() < 1e-9


def test_axial_resolution_is_27mm():
    dz = fresnel.axial_resolution(LED_RED.wavelength, DLP4500.aperture_short, 0.5)
    assert 0.02 < dz < 0.04


def test_groups_partition_and_pooling():
    assert signed_depth.groups_partition((128, 128))
    each, p, cross = signed_depth.pool_crosses([0.4, 0.4, 0.4], 1.0)
    assert each and cross and abs(p - 1.2) < 1e-12


def test_hadamard():
    assert nlos.hadamard_orthogonality_residual(6) < 1e-9


def test_bmp_roundtrip(tmpdir="/tmp"):
    rng = np.random.default_rng(4)
    p = rng.integers(0, 2, size=(64, 96)).astype(np.uint8)
    path = os.path.join(tmpdir, "_ogr_rt.bmp")
    bmp.write_bmp1(path, p)
    assert np.array_equal(bmp.read_bmp1(path), p)
    os.remove(path)


def test_end_to_end_correlation():
    N = 1024
    g = pipeline.text_glyph("X", int(N * 0.125))
    canvas = np.zeros((N, N))
    s = g.shape[0]
    c0 = (N - s) // 2
    canvas[c0:c0 + s, c0:c0 + s] = g
    H = pipeline.gerchberg_saxton(canvas, iters=40)
    B = lee.encode_field(H, f_c=0.125, axis="u")
    from ogr.fourier import reconstruct, intensity
    img = intensity(reconstruct(B.astype(float)))
    cj = N // 2 + int(0.125 * N)
    r = s // 2
    win = img[N // 2 - r:N // 2 + r, cj - r:cj + r]
    win = win / win.max()
    tgt = g[np.arange(win.shape[0]) * s // win.shape[0]][
        :, np.arange(win.shape[1]) * s // win.shape[1]]
    assert float(np.corrcoef(win.ravel(), tgt.ravel())[0, 1]) > 0.9


def test_offaxis_guard():
    try:
        pipeline.run([pipeline.text_glyph("X", 128)], "/tmp/_g",
                     fill_fraction=0.5, encode_size=256, write_files=False)
    except ValueError:
        return
    raise AssertionError("off-axis guard did not fire")


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    npass = 0
    for name, fn in fns:
        try:
            fn()
            print("PASS  %s" % name)
            npass += 1
        except Exception as e:
            print("FAIL  %s : %s" % (name, e))
    print("-" * 50)
    print("%d/%d tests passed" % (npass, len(fns)))
    raise SystemExit(0 if npass == len(fns) else 1)
