"""
OGR DMD Math Package v1.0
Operation Glyph Retrieval — executable mathematics for DMD holography.

Consolidates Messina Nullification Framework corpus outputs 87-94 into a
single numerically-validated Python package with hardware constants, a
reconstruction model, binary hologram encoding, axial depth encoding,
Babinet/conservation checks, NLoS projection duality, and DLPC350 export.

Modules
    hardware     DLP4500 / DLP3010ULC constants, Fraunhofer, sampling
    fourier      DMD-as-Fourier-plane reconstruction model
    babinet      ON/OFF complementarity, N + R = identity check
    diagonal     45-degree zero-line reference, depth trichotomy, diamond
    lee          binary hologram encoding, carrier, order coefficients
    fresnel      axial depth via quadratic phase, resolution limits
    signed_depth +/-0.0e mirror groups, PWM pool accumulation
    nlos         Lambertian transport, Hadamard, constrained projection
    bmp          1-bit and 24-bit BMP export for the LightCrafter GUI
    pipeline     glyph -> pattern set -> manifest
    validate     one-call self-check of every claim in the package
"""

__version__ = "1.0"

from . import hardware, fourier, babinet, diagonal, lee, fresnel
from . import signed_depth, nlos, bmp, pipeline

__all__ = [
    "hardware", "fourier", "babinet", "diagonal", "lee", "fresnel",
    "signed_depth", "nlos", "bmp", "pipeline", "__version__",
]
