"""
ogr.fourier — the DMD-as-Fourier-plane model.

CORE IDENTITY (output 90, Lean: OGR93.reconstruction = Real.fourierIntegral)

    U_recon(x, y) = (e^{ikz} / (i*lambda*z)) * e^{ik(x^2+y^2)/(2z)}
                    * F[t(u,v)] evaluated at (f_x, f_y) = (x/(lambda z), y/(lambda z))

Everything downstream in this package assumes:
  * t(u,v) is the DMD complex transmittance (binary real for a bare DMD)
  * the quadratic phase prefactor is irrelevant to INTENSITY, which is
    what a wall or an eye records, so it is dropped by default
  * discrete sampling: p = mirror pitch, N samples -> reconstruction sample
    spacing dx = lambda*z/(N*p), full window lambda*z/p

[PROVED] in Lean (output 90/93): reconstruction(F^{-1}[g]) = g, via
Mathlib Continuous.fourier_inversion_inv. The numerical analogue here is
`inversion_residual`, which must be at machine precision.
"""

import numpy as np

from .hardware import recon_pixel_pitch, recon_field_of_view


def reconstruct(pattern, shift=True):
    """
    Complex FAR-FIELD of a DMD pattern (plain 2-D DFT).

    VALID ONLY IF one of these holds:
      (a) the Fresnel number a^2/(lambda z) <= ~0.1, or
      (b) a Fourier-transforming lens is present and you are observing its
          back focal plane, or
      (c) the pattern itself carries a Fresnel lens phase (ogr.fresnel), in
          which case this DFT is the reconstruction at that focal distance.

    For a bare DLP4500 at z = 0.5 m none of (a) holds: N_F ~ 37. Use
    `fresnel_reconstruct` or encode a lens phase. See docs/CORRECTIONS.md.

    pattern : 2-D real or complex array (mirror transmittance, ON=1 OFF=0)
    returns : complex 2-D array, same shape, DC at centre if shift=True
    """
    a = np.asarray(pattern, dtype=complex)
    f = np.fft.fft2(a)
    return np.fft.fftshift(f) if shift else f


def intensity(field):
    """Recorded quantity on a wall / sensor / retina."""
    return np.abs(field) ** 2


def inverse(field, shift=True):
    """Inverse of `reconstruct` (pattern synthesis from a desired field)."""
    f = np.fft.ifftshift(np.asarray(field, dtype=complex)) if shift else np.asarray(field, dtype=complex)
    return np.fft.ifft2(f)


def inversion_residual(pattern):
    """
    [PROVED-numeric] F^{-1}[F[t]] = t. Returns max abs residual.
    Kill criterion: must be < 1e-10 for float64.
    """
    a = np.asarray(pattern, dtype=complex)
    back = inverse(reconstruct(a))
    return float(np.max(np.abs(back - a)))


def recon_axes(shape, wavelength, z, pitch):
    """
    Physical coordinates (metres) of the reconstruction plane samples.
    Returns (x_axis, y_axis) with x along axis 1 (columns).
    """
    ny, nx = shape
    dx = recon_pixel_pitch(wavelength, z, nx, pitch)
    dy = recon_pixel_pitch(wavelength, z, ny, pitch)
    x = (np.arange(nx) - nx // 2) * dx
    y = (np.arange(ny) - ny // 2) * dy
    return x, y


def recon_report(shape, wavelength, z, pitch):
    """Human/agent readable sampling summary for a given configuration."""
    ny, nx = shape
    return {
        "shape": (ny, nx),
        "wavelength_m": wavelength,
        "z_m": z,
        "dmd_pitch_m": pitch,
        "recon_dx_m": recon_pixel_pitch(wavelength, z, nx, pitch),
        "recon_dy_m": recon_pixel_pitch(wavelength, z, ny, pitch),
        "fov_x_m": recon_field_of_view(wavelength, z, pitch),
        "fov_y_m": recon_field_of_view(wavelength, z, pitch),
        "angular_fov_rad": wavelength / pitch,
        "note": "angular FOV equals one grating-order separation lambda/p",
    }


def fresnel_reconstruct(pattern, wavelength, z, pitch, shift=True):
    """
    [ASSERTED, standard] Single-FFT Fresnel transform — the correct
    reconstruction operator for the actual OGR geometry (near field).

        U(x,y;z) ~ F[ t(u,v) * exp(i*pi*(u^2+v^2)/(lambda*z)) ]

    evaluated at (x/(lambda z), y/(lambda z)). Output sample spacing is the
    same lambda*z/(N*p) as the Fraunhofer case, so all sampling formulas in
    ogr.hardware carry over unchanged. Only the operator changes.

    Note the sign: the source-plane chirp here is +i (it cancels the
    propagation curvature). A lens phase written into the pattern
    (ogr.fresnel.lens_phase, which is -i) cancels this chirp exactly, which
    is why a Fresnel-lens-encoded hologram reconstructs under the plain DFT.
    """
    a = np.asarray(pattern, dtype=complex)
    ny, nx = a.shape
    y, x = np.indices((ny, nx))
    u = (x - nx // 2) * pitch
    v = (y - ny // 2) * pitch
    chirp = np.exp(1j * np.pi * (u * u + v * v) / (wavelength * z))
    f = np.fft.fft2(np.fft.ifftshift(a * chirp))
    return np.fft.fftshift(f) if shift else f


def bandwidth_of(field, threshold=0.01):
    """
    Estimate the normalised spatial bandwidth B of a field (fraction of the
    Nyquist band that carries >= `threshold` of peak spectral magnitude).
    Used by the off-axis carrier condition f_c >= 1.5 * B.
    """
    spec = np.abs(reconstruct(field))
    if spec.max() == 0:
        return 0.0
    ny, nx = spec.shape
    mask = spec >= threshold * spec.max()
    ys, xs = np.nonzero(mask)
    rx = np.max(np.abs(xs - nx // 2)) / (nx / 2.0)
    ry = np.max(np.abs(ys - ny // 2)) / (ny / 2.0)
    return float(max(rx, ry) * 0.5)  # in cycles/sample, Nyquist = 0.5
