"""
ogr.hardware — DMD and geometry constants for Operation Glyph Retrieval (OGR).

All constants are SI unless the name says otherwise.
Sources: TI DLPU011E (DLP LightCrafter 4500), TI DLP3010 datasheet,
Goodman "Introduction to Fourier Optics" (Fraunhofer condition),
Born & Wolf (van Cittert-Zernike).

Register tags follow the Messina Nullification Framework convention:
  [PROVED]     arithmetic or Lean-verified
  [ASSERTED]   standard physics / datasheet value, not proved here
  [HEURISTIC]  interpretive mapping
"""

from dataclasses import dataclass, asdict
import math

C_LIGHT = 299_792_458.0


@dataclass(frozen=True)
class DMD:
    """A digital micromirror device."""
    name: str
    n_rows: int            # mirrors along the short axis
    n_cols: int            # mirrors along the long axis
    pitch: float           # metres, mirror-to-mirror
    tilt_deg: float        # +/- mirror tilt about its hinge
    smooth_axis_deg: float # natural smooth axis of the pixel lattice
    diamond: bool          # True if diamond (45-deg offset rows) lattice
    binary_rate_hz: float  # max 1-bit pattern rate
    gray_rate_hz: float    # max 8-bit pattern rate
    min_exposure_s: float  # minimum 1-bit exposure

    @property
    def n_mirrors(self) -> int:
        """[PROVED] Total addressable mirrors."""
        return self.n_rows * self.n_cols

    @property
    def aperture_short(self) -> float:
        """[PROVED] Active aperture along the short axis, metres."""
        return self.n_rows * self.pitch

    @property
    def aperture_long(self) -> float:
        """[PROVED] Active aperture along the long axis, metres."""
        return self.n_cols * self.pitch

    def fraunhofer_threshold(self, wavelength: float, axis: str = "long") -> float:
        """
        [ASSERTED] Far-field (Fraunhofer) onset distance, z >> a^2 / lambda.
        RETURNS METRES.

        !! UNIT CORRECTION TO OUTPUT 90 !!
        Output 90's header computes 6.89e-3^2 / 528e-9 ~= 90 and labels the
        result "90 mm". The result is 90 METRES. Same for the "55 mm" red
        figure (correct value 74.5 m on the short axis, 116.4 m on the long
        axis). The conclusion drawn there — "at z = 500 mm we are solidly in
        the Fraunhofer regime" — is therefore false by three orders of
        magnitude. See docs/CORRECTIONS.md; this is the single most important
        correction in the package.
        """
        a = self.aperture_long if axis == "long" else self.aperture_short
        return a * a / wavelength

    def fresnel_number(self, wavelength: float, z: float,
                       half_aperture: float = None) -> float:
        """
        [PROVED] N_F = a^2 / (lambda z) with a the HALF-aperture.
        N_F << 1 -> Fraunhofer (far field). N_F >> 1 -> Fresnel (near field).
        At z = 0.5 m the DLP4500 full array gives N_F ~ 37 (red), i.e. deep
        near field.
        """
        a = half_aperture if half_aperture is not None else self.aperture_short / 2.0
        return a * a / (wavelength * z)

    def is_far_field(self, wavelength: float, z: float,
                     half_aperture: float = None, tol: float = 0.1) -> bool:
        """[PROVED] Far field iff N_F <= tol."""
        return self.fresnel_number(wavelength, z, half_aperture) <= tol

    def max_far_field_aperture(self, wavelength: float, z: float,
                               tol: float = 0.1) -> float:
        """
        [PROVED] Largest half-aperture that is genuinely in the far field at
        distance z: a_max = sqrt(tol * lambda * z). Divide by pitch for the
        usable mirror count.
        """
        return (tol * wavelength * z) ** 0.5

    def far_field_mirror_count(self, wavelength: float, z: float,
                               tol: float = 0.1) -> int:
        """Number of mirrors across the far-field-valid sub-aperture."""
        return int(2.0 * self.max_far_field_aperture(wavelength, z, tol) / self.pitch)

    def order_separation_rad(self, wavelength: float) -> float:
        """
        [ASSERTED] Angular spacing of grating orders for a periodic mirror
        array: sin(theta_{m+1}) - sin(theta_m) = lambda / p. Small-angle,
        this is the angular width of one diffraction order — and therefore
        the angular field of view of a single reconstruction.
        """
        return wavelength / self.pitch

    def blaze_angle_deg(self) -> float:
        """[ASSERTED] Specular (blaze) direction is 2x the mirror tilt."""
        return 2.0 * self.tilt_deg


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

DLP4500 = DMD(
    name="DLP LightCrafter 4500 (DLP4500)",
    n_rows=912,
    n_cols=1140,
    pitch=7.56e-6,
    tilt_deg=12.0,
    smooth_axis_deg=45.0,     # diamond lattice -> diagonal is the smooth axis
    diamond=True,
    binary_rate_hz=4225.0,
    gray_rate_hz=120.0,
    min_exposure_s=235e-6,
)

DLP3010ULC = DMD(
    name="DLP3010 (ULC variant)",
    n_rows=720,
    n_cols=1280,
    pitch=5.4e-6,
    tilt_deg=17.0,
    smooth_axis_deg=0.0,      # orthogonal lattice -> horizontal smooth axis
    diamond=False,
    binary_rate_hz=4225.0,
    gray_rate_hz=120.0,
    min_exposure_s=235e-6,
)


# ---------------------------------------------------------------------------
# Illumination
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    name: str
    wavelength: float        # metres, peak
    bandwidth: float         # metres, FWHM
    coherence_length: float  # metres, measured spatial coherence radius

    @property
    def temporal_coherence_length(self) -> float:
        """[ASSERTED] L_c = lambda^2 / delta-lambda."""
        return self.wavelength ** 2 / self.bandwidth


LED_RED = Source("Red LED (~638 nm)", 638e-9, 20e-9, 24e-6)
LED_GREEN = Source("Green LED (~528 nm)", 528e-9, 30e-9, 5.8e-6)
LED_BLUE = Source("Blue LED (~460 nm)", 460e-9, 25e-9, 4.0e-6)


# ---------------------------------------------------------------------------
# Two-stage OGR geometry (output 91)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Geometry:
    """
    Stage 1: DMD -> relay wall (in-focus projection, Lambertian scatter).
    Stage 2: relay wall -> reconstruction plane (Fraunhofer holography).
    """
    d_dmd_wall: float = 0.5     # metres
    d_wall_recon: float = 0.5   # metres
    wall_albedo: float = 0.85   # Lambertian reflectance of matte white
    focus_min: float = 0.5      # DLP4500 focus range, metres
    focus_max: float = 2.0
    throw_ratio: float = 1.4

    @property
    def d_total(self) -> float:
        """[PROVED] Total DMD-to-glyph path length."""
        return self.d_dmd_wall + self.d_wall_recon

    @property
    def wall_spot_width(self) -> float:
        """[ASSERTED] Illuminated wall width = d / throw_ratio."""
        return self.d_dmd_wall / self.throw_ratio

    def wall_coherence_radius(self, wavelength: float) -> float:
        """
        [ASSERTED] van Cittert-Zernike coherence radius at the observation
        plane for an incoherent secondary source of width a_wall:
            r_coh = 1.22 * lambda * d / a_wall
        """
        return 1.22 * wavelength * self.d_wall_recon / self.wall_spot_width


OGR_GEOMETRY = Geometry()


# ---------------------------------------------------------------------------
# Reconstruction sampling — the numbers a builder actually needs
# ---------------------------------------------------------------------------

def recon_pixel_pitch(wavelength: float, z: float, n: int, dmd_pitch: float) -> float:
    """
    [PROVED] Sample spacing in the reconstruction plane for an N-point DFT
    of a pattern with mirror pitch p at distance z:

        dx_recon = lambda * z / (N * p)

    This is the standard Fraunhofer/DFT correspondence f_x = x / (lambda z)
    combined with the DFT bin spacing df = 1 / (N p).
    """
    return wavelength * z / (n * dmd_pitch)


def recon_field_of_view(wavelength: float, z: float, dmd_pitch: float) -> float:
    """
    [PROVED] Full width of one reconstruction (one diffraction order):

        FOV = lambda * z / p

    Equivalently, angular FOV = lambda / p = the grating order separation.
    The DFT window and one diffraction order coincide exactly.
    """
    return wavelength * z / dmd_pitch


def fringe_visibility(pinhole_diameter: float, wavelength: float,
                      z: float, aperture: float) -> float:
    """
    [ASSERTED] van Cittert-Zernike fringe visibility for a circular
    incoherent source of diameter d seen across an aperture a at range z.
    Uses the Airy modulus |2 J1(v)/v| with
        v = pi * d * a / (lambda * z).
    Returns |mu_12| in [0, 1].
    """
    v = math.pi * pinhole_diameter * aperture / (wavelength * z)
    if v == 0.0:
        return 1.0
    # J1 from Bessel's integral (no scipy needed)
    j1 = _bessel_j1(v)
    return abs(2.0 * j1 / v)


def _bessel_j1(x: float) -> float:
    """J1 from Bessel's integral J1(x) = (1/2pi) * integral over one period of cos(t - x sin t) dt.
    The integrand is smooth and periodic, so the equally spaced (trapezoid) sum converges exponentially once
    the node count exceeds |x|; 64 + 2|x| nodes give ~1e-15 here. (Replaces a rational approximation.)"""
    n = 64 + 2 * int(abs(x))
    return sum(math.cos(t - x * math.sin(t)) for t in (2.0 * math.pi * k / n for k in range(n))) / n


def as_dict():
    """Machine-readable dump of every constant, for the receiving agent."""
    return {
        "devices": {
            "DLP4500": asdict(DLP4500),
            "DLP3010ULC": asdict(DLP3010ULC),
        },
        "sources": {
            "red": asdict(LED_RED),
            "green": asdict(LED_GREEN),
            "blue": asdict(LED_BLUE),
        },
        "geometry": asdict(OGR_GEOMETRY),
        "derived": {
            "dlp4500_n_mirrors": DLP4500.n_mirrors,
            "dlp4500_aperture_short_m": DLP4500.aperture_short,
            "dlp4500_aperture_long_m": DLP4500.aperture_long,
            "fraunhofer_red_short_m": DLP4500.fraunhofer_threshold(LED_RED.wavelength, "short"),
            "fraunhofer_red_long_m": DLP4500.fraunhofer_threshold(LED_RED.wavelength, "long"),
            "fraunhofer_green_short_m": DLP4500.fraunhofer_threshold(LED_GREEN.wavelength, "short"),
            "fraunhofer_green_long_m": DLP4500.fraunhofer_threshold(LED_GREEN.wavelength, "long"),
            "recon_fov_red_500mm_m": recon_field_of_view(LED_RED.wavelength, 0.5, DLP4500.pitch),
            "recon_pixel_red_500mm_N1140_m": recon_pixel_pitch(
                LED_RED.wavelength, 0.5, 1140, DLP4500.pitch),
        },
    }
