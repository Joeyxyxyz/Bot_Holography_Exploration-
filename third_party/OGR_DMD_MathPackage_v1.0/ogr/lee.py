"""
ogr.lee — binary hologram encoding for a two-level device.

The DMD is binary: every mirror is exactly 0 or 1. A glyph hologram is a
complex field H = A * exp(i*phi). The Lee method writes H onto a binary
array by modulating the DUTY CYCLE of a carrier fringe:

    B(u, v) = 1   iff   cos(2*pi*f_c*u + phi(u,v)) >= cos(pi*A(u,v))
    B(u, v) = 0   otherwise                                        (A in [0,1])

WHAT THE FIRST ORDER ACTUALLY CARRIES  [PROVED]
--------------------------------------------------------------------------
For fixed (A, phi), B is the indicator of an arc of angular width 2*pi*A
centred at -phi. Its Fourier coefficients in the carrier harmonics are

    c_m = exp(i*m*phi) * sin(m*pi*A) / (m*pi)

so the m = +1 order recovers

    c_1 = (1/pi) * sin(pi*A) * exp(i*phi).

Consequences you must not skip:

  1. The PHASE is recovered exactly.
  2. The AMPLITUDE is recovered as sin(pi*A)/pi, NOT as A. This is a hard
     nonlinearity. `encode` applies the pre-compensation A_enc =
     arcsin(A_target)/pi by default so that c_1 = A_target/pi exactly.
  3. Peak first-order amplitude efficiency is 1/pi (A = 1/2), i.e. 1/pi^2
     ~= 10.1% in intensity. That is the textbook binary-amplitude-grating
     figure and it is the ceiling. Output 94's phrase "F[B] at f_c exactly
     recovers H" is true only up to this 1/pi factor and only in the +1
     order; the DC term and every odd harmonic are still present.
  4. Even harmonics vanish only at A = 1/2. General A leaves an m = 2 term
     of magnitude sin(2*pi*A)/(2*pi) which lands at 2*f_c. Keep 2*f_c
     outside the window or accept the ghost.

OFF-AXIS SEPARATION  [ASSERTED, standard off-axis holography]
    f_c >= 1.5 * B_glyph          (glyph, DC and twin do not overlap)
    f_c <= 0.5                    (Nyquist, cycles per mirror)
Lateral position of the reconstructed glyph in the recon plane:
    x_glyph = f_c * lambda * z / p = f_c * FOV

CARRIER SAMPLING — measured, not assumed
--------------------------------------------------------------------------
c_1 = sin(pi*A)/pi is the CONTINUOUS-limit coefficient. On a sampled grid
the carrier has only 1/f_c samples per period and the binarisation lands on
grid points, so the realised coefficient deviates:

    f_c = 0.250   ( 4 samples/period)  measured |c_1| = 0.2813  (-11.6%)
    f_c = 0.125   ( 8 samples/period)  measured |c_1| = 0.3082  ( -3.2%)
    f_c = 0.0625  (16 samples/period)  measured |c_1| = 0.3158  ( -0.8%)
    f_c = 0.03125 (32 samples/period)  measured |c_1| = 0.3177  ( -0.2%)
    continuous limit                              sin(pi/2)/pi = 0.3183

Output 94's text says "typically 1/4 of Nyquist", i.e. f_c = 0.125, and that
is the package default. Do not raise it to 0.25 to buy separation without
also accepting the 20% amplitude loss.
"""

import numpy as np

from .fourier import reconstruct, bandwidth_of


def encode(amplitude, phase, f_c=0.125, axis="u", linearise=True):
    """
    Lee-encode a complex field onto a binary DMD pattern.

    amplitude : real array in [0, 1]
    phase     : real array, radians
    f_c       : carrier frequency, cycles per mirror (0 < f_c <= 0.5)
    axis      : "u" (carrier along columns/x) or "v" (along rows/y)
                or "diag" (carrier along the DLP4500 smooth 45-deg axis)
    linearise : pre-compensate the sin(pi*A) nonlinearity

    returns : uint8 array of 0/1
    """
    A = np.clip(np.asarray(amplitude, dtype=float), 0.0, 1.0)
    ph = np.asarray(phase, dtype=float)
    if A.shape != ph.shape:
        raise ValueError("amplitude and phase must have the same shape")
    if not (0.0 < f_c <= 0.5):
        raise ValueError("carrier must satisfy 0 < f_c <= 0.5 cycles/mirror")

    A_enc = np.arcsin(A) / np.pi if linearise else A

    ny, nx = A.shape
    i, j = np.indices((ny, nx))
    if axis == "u":
        carrier = 2.0 * np.pi * f_c * j
    elif axis == "v":
        carrier = 2.0 * np.pi * f_c * i
    elif axis == "diag":
        carrier = 2.0 * np.pi * f_c * (j - i) / np.sqrt(2.0)
    else:
        raise ValueError("axis must be 'u', 'v' or 'diag'")

    B = (np.cos(carrier + ph) >= np.cos(np.pi * A_enc)).astype(np.uint8)
    return B


def encode_field(field, f_c=0.125, axis="u", linearise=True, normalise=True):
    """Convenience wrapper: encode a complex ndarray directly."""
    H = np.asarray(field, dtype=complex)
    A = np.abs(H)
    if normalise and A.max() > 0:
        A = A / A.max()
    return encode(A, np.angle(H), f_c=f_c, axis=axis, linearise=linearise)


def is_binary(pattern):
    """[PROVED] Every element is exactly 0 or 1."""
    a = np.asarray(pattern)
    return bool(np.all((a == 0) | (a == 1)))


def theoretical_order_coefficient(A, phase, m=1):
    """[PROVED] c_m = exp(i*m*phi) * sin(m*pi*A) / (m*pi)."""
    A = np.asarray(A, dtype=float)
    phase = np.asarray(phase, dtype=float)
    return np.exp(1j * m * phase) * np.sin(m * np.pi * A) / (m * np.pi)


def first_order_efficiency(A=0.5):
    """[PROVED] Intensity efficiency of the +1 order: (sin(pi*A)/pi)^2."""
    return (np.sin(np.pi * A) / np.pi) ** 2


def extract_order(pattern, f_c=0.125, axis="u", radius=None):
    """
    Demodulate the +1 order out of a binary hologram's transform.
    Returns the complex field in a window centred on the carrier.
    """
    F = reconstruct(pattern)
    ny, nx = F.shape
    if axis == "u":
        cx, cy = int(round(f_c * nx)), 0
    elif axis == "v":
        cx, cy = 0, int(round(f_c * ny))
    else:
        cx = int(round(f_c * nx / np.sqrt(2.0)))
        cy = -cx
    ci, cj = ny // 2 + cy, nx // 2 + cx
    if radius is None:
        radius = min(nx, ny) // 8
    return F[ci - radius:ci + radius, cj - radius:cj + radius], (ci, cj)


def off_axis_ok(field, f_c, threshold=0.01):
    """
    [ASSERTED] Off-axis separation criterion f_c >= 1.5 * B_glyph, with the
    glyph bandwidth measured from the field itself.
    Returns (ok, B_glyph, f_c_min).
    """
    B = bandwidth_of(field, threshold=threshold)
    f_min = 1.5 * B
    return bool(f_c >= f_min and f_c <= 0.5), float(B), float(f_min)


def samples_per_carrier_period(f_c):
    """[PROVED] 1 / f_c. Below ~8 the continuous-limit coefficient is wrong."""
    return 1.0 / f_c


def measured_first_order(f_c, n=512, A=0.5):
    """
    Empirical |c_1| for a uniform-amplitude carrier at this f_c and grid size.
    Use this instead of the closed form when f_c is coarse.
    """
    A_arr = np.full((n, n), A)
    B = encode(A_arr, np.zeros((n, n)), f_c=f_c, axis="u", linearise=False)
    F = np.fft.fftshift(np.fft.fft2(B)) / B.size
    cj = n // 2 + int(round(f_c * n))
    return float(np.abs(F[n // 2, cj]))


def glyph_offset_metres(f_c, wavelength, z, pitch):
    """[PROVED] Lateral displacement of the +1 order in the recon plane."""
    return f_c * wavelength * z / pitch
