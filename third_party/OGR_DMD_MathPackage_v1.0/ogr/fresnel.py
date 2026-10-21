"""
ogr.fresnel — axial (z) structure. Read the correction block before using
anything downstream of this module.

CORRECTION TO OUTPUTS 92 AND 93 — this is the substantive one
==========================================================================
Outputs 92/93 encode "positive depth" and "negative depth" layers by giving
the M+ and M- mirror groups carriers of opposite sign, and quote

    d_pos = lambda_r * f_sampling / (2 * sin(theta+))

as the reconstruction distance. Two problems:

  (a) DIMENSIONS. lambda [m] * f_sampling [1/m] is dimensionless. Divided by
      sin(theta) it is still dimensionless. It cannot be a distance. The
      formula as written does not define a depth.

  (b) MECHANISM. A carrier of opposite sign moves the reconstruction to the
      opposite side of the DC term IN THE SAME PLANE. That is a LATERAL
      displacement, x = +/- f_c * lambda * z / p. It is not axial. Two
      opposite carriers give you two glyphs left and right of centre at the
      same z, not two depth planes.

Axial separation requires a QUADRATIC phase term, not a linear one. A linear
phase ramp translates; a quadratic phase refocuses. The correct encoding of a
layer at axial distance z_k is to multiply that layer's field by a Fresnel
lens factor

    L(x, y; f) = exp(-i * pi * (x^2 + y^2) / (lambda * f)),    f = z_k

before summing the layers and Lee-encoding the total. Then:

    f > 0  ->  converging  ->  real image forms in front of the nominal
                              plane                       [ the +0.0e layer ]
    f < 0  ->  diverging   ->  virtual image behind        [ the -0.0e layer ]
    f -> inf ->  no curvature -> content stays at the nominal plane
                                                            [ the [0] ground ]

That IS the signed trichotomy, and it is physically real. The sign of the
quadratic phase is the sign of the reservoir state. Keep the diagonal-stripe
reference and the +/- carrier for LATERAL order separation, which is what
they are good for, and use the lens phase for depth. The two mechanisms are
independent and compose.

AXIAL RESOLUTION — a hard design constraint
--------------------------------------------------------------------------
    NA = a_coh / (2 z),        delta_z ~= 2 * lambda / NA^2

a_coh is the COHERENT aperture. For direct DLP4500 holography that is the
DMD active area, ~6.89 mm, giving at z = 0.5 m and lambda = 638 nm

    NA = 6.89e-3,   delta_z ~= 2.7e-2 m = 27 mm.

Layers closer together than ~27 mm are not axially resolvable, full stop.
Wall-bounce enlarges the GEOMETRIC aperture but not the coherent one, so it
does not by itself buy axial resolution. Design your depth ladder on 27 mm
steps or better, and pre-register that number before you run the experiment.
"""

import numpy as np


def lens_phase(shape, wavelength, focal_length, dx):
    """
    [ASSERTED, standard Fourier optics] Thin-lens quadratic phase factor
    exp(-i*pi*r^2/(lambda*f)) sampled on a grid of pitch dx.
    focal_length may be negative (diverging / virtual image).
    """
    ny, nx = shape
    y, x = np.indices((ny, nx))
    x = (x - nx // 2) * dx
    y = (y - ny // 2) * dx
    r2 = x * x + y * y
    return np.exp(-1j * np.pi * r2 / (wavelength * focal_length))


def propagate(field, wavelength, z, dx):
    """
    [ASSERTED] Angular-spectrum propagation over distance z.
    Exact for scalar diffraction within the sampled band; no paraxial
    approximation. dx is the sample pitch in the source plane.
    """
    U = np.asarray(field, dtype=complex)
    ny, nx = U.shape
    fx = np.fft.fftfreq(nx, d=dx)
    fy = np.fft.fftfreq(ny, d=dx)
    FX, FY = np.meshgrid(fx, fy)
    arg = 1.0 - (wavelength * FX) ** 2 - (wavelength * FY) ** 2
    evanescent = arg < 0
    kz = 2.0 * np.pi / wavelength * np.sqrt(np.clip(arg, 0.0, None))
    H = np.exp(1j * kz * z)
    H[evanescent] = 0.0            # evanescent -> the [0.0e] reservoir
    return np.fft.ifft2(np.fft.fft2(U) * H)


def evanescent_fraction(shape, wavelength, dx):
    """
    [HEURISTIC->PROVED-numeric] Fraction of the sampled spatial-frequency
    band that is evanescent (does not propagate). In MNF terms this is the
    portion of the pattern's content that stays in the [0.0e] reservoir:
    it exists in the aperture and contributes nothing observable at z > 0.
    """
    ny, nx = shape
    fx = np.fft.fftfreq(nx, d=dx)
    fy = np.fft.fftfreq(ny, d=dx)
    FX, FY = np.meshgrid(fx, fy)
    arg = 1.0 - (wavelength * FX) ** 2 - (wavelength * FY) ** 2
    return float(np.mean(arg < 0))


def numerical_aperture(coherent_aperture, z):
    """[PROVED] NA = a / (2 z)."""
    return coherent_aperture / (2.0 * z)


def axial_resolution(wavelength, coherent_aperture, z):
    """[ASSERTED] delta_z = 2 * lambda / NA^2. Minimum resolvable layer gap."""
    na = numerical_aperture(coherent_aperture, z)
    return 2.0 * wavelength / (na * na)


def lateral_resolution(wavelength, coherent_aperture, z):
    """[ASSERTED] delta_x = lambda / (2 NA) = lambda z / a."""
    na = numerical_aperture(coherent_aperture, z)
    return wavelength / (2.0 * na)


def encode_layers(layers, wavelength, dx, focal_lengths):
    """
    Build a single complex field encoding several axial layers.

    layers        : list of 2-D real or complex arrays (the content per layer)
    focal_lengths : list of signed focal lengths, one per layer.
                    +f -> real image at +f   (MNF: +0.0e reservoir)
                    -f -> virtual image at -f (MNF: -0.0e reservoir)
                    np.inf -> stays at the nominal plane (MNF: [0] ground)

    returns : complex field ready for ogr.lee.encode_field
    """
    if len(layers) != len(focal_lengths):
        raise ValueError("one focal length per layer")
    total = np.zeros(np.asarray(layers[0]).shape, dtype=complex)
    for layer, f in zip(layers, focal_lengths):
        L = np.asarray(layer, dtype=complex)
        if np.isinf(f):
            total = total + L
        else:
            total = total + L * lens_phase(L.shape, wavelength, f, dx)
    return total


def depth_ladder(z_min, z_max, wavelength, coherent_aperture, z_nominal):
    """
    Largest set of axially resolvable layers between z_min and z_max,
    spaced by the axial resolution. Returns the list of focal lengths.
    """
    dz = axial_resolution(wavelength, coherent_aperture, z_nominal)
    n = int(np.floor((z_max - z_min) / dz)) + 1
    return [z_min + k * dz for k in range(max(n, 1))], dz
