# AGENT BRIEF — read this first

You are being handed a self-contained mathematics + reference-implementation
package for **Operation Glyph Retrieval (OGR)**: holographic glyph projection
from a Texas Instruments DLP digital micromirror device.

This brief is written for an autonomous coding agent. It is fully
self-contained: you do not need any prior conversation, any external
repository, or any file outside this directory.

---

## 0. Do this first, before writing any code

```bash
cd OGR_DMD_MathPackage_v1.0
python3 -m ogr.validate
```

Expected output: `31/31 checks passed`, exit code 0.

Requires Python 3.9+ and NumPy. Nothing else. No Pillow, no SciPy, no network.

If any check fails, **stop and report which one**. Do not proceed, do not
loosen a tolerance, and do not "fix" a failing check by changing its
threshold. Every tolerance in `ogr/validate.py` is a pre-registered kill
criterion, not a knob.

---

## 1. What the package is

Nine modules under `ogr/`, each covering one layer of the optical chain:

| module | covers | primary claim |
|---|---|---|
| `hardware` | DLP4500 / DLP3010ULC constants, Fresnel number, sampling | far-field validity, FOV, resolution |
| `fourier` | reconstruction operator | `F^-1[F[t]] = t`, Fresnel vs Fraunhofer |
| `babinet` | ON/OFF complementarity | `F[ON] + F[OFF] = F[full]` |
| `diagonal` | 45° zero-line reference | stripe along (1,1) → recon line along (1,−1) |
| `lee` | binary hologram encoding | `c_1 = sin(πA)e^{iφ}/π` |
| `fresnel` | axial depth, resolution limits | depth is quadratic phase, not linear |
| `signed_depth` | ±0.0e mirror groups, PWM pooling | partition + pool accumulation |
| `nlos` | Lambertian transport, Hadamard | projection is the dual of reconstruction |
| `bmp`, `pipeline` | DLPC350 export, glyph → pattern | end-to-end, correlation 0.977 |

---

## 2. The five corrections you must not undo

The package **corrects five errors** in the source material it was built
from. Full detail in `docs/CORRECTIONS.md`. Summary:

1. **Fraunhofer distance is metres, not millimetres.** `a²/λ ≈ 90` is 90 m,
   not 90 mm. At z = 0.5 m the Fresnel number is ~37: this is the **near
   field**. A bare DMD at 500 mm does not produce a Fraunhofer
   reconstruction. Fix: encode a Fresnel lens phase into the pattern
   (`ogr.fresnel.lens_phase`), or put a physical Fourier lens in the path.
   The package does the former by default.
2. **Depth is a quadratic phase, not a signed carrier.** Opposite-sign
   carriers give left/right lateral offset in one plane, not two depth
   planes. Axial placement requires `exp(-iπr²/(λf))`.
3. **The depth trichotomy needs one functional, not two.** Define all three
   regions by `⟨DiagDir, w⟩`. See `docs/LEAN_PATCH.md`.
4. **Encode the hologram, not the image.** Lee-encode `F^-1[glyph]`, with a
   random or Gerchberg-Saxton phase. Encoding the glyph directly reconstructs
   its transform.
5. **Off-axis needs headroom.** `fill_fraction ≤ 1.33·f_c`. Measured: fill
   0.25 gives correlation −0.0003; fill 0.125 gives 0.977.

---

## 3. Minimal working example

```python
import numpy as np
from ogr import pipeline

glyph = pipeline.text_glyph("X", 512)          # or any 2-D non-negative array

manifest = pipeline.run(
    glyphs=[glyph],
    outdir="out/",
    focal_lengths=[np.inf],   # np.inf = at the nominal plane
    encode_size=1024,
    f_c=0.125,                # carrier, cycles per mirror
)
```

Writes `out/ogr_pattern_000.bmp` (1-bit, 912×1140), a 24-bit copy, and
`out/manifest.json` recording every parameter used.

Two depth layers:

```python
manifest = pipeline.run([glyph_a, glyph_b], "out/",
                        focal_lengths=[0.5, -0.5])   # metres, signed
```

`+f` → real image in front. `−f` → virtual image behind. `np.inf` → nominal
plane. Layers closer than the axial resolution (**26.8 mm** at z = 0.5 m,
λ = 638 nm, full DMD aperture) are not resolvable — the package computes this
for your parameters in `manifest["resolution"]["axial_resolution_m"]`.

---

## 4. Tasks, in priority order

**T1 — Reproduce validation.** Run `python3 -m ogr.validate`. Report the
table verbatim. Do not modify it.

**T2 — Sweep and report, do not tune silently.** For
`f_c ∈ {0.0625, 0.125, 0.25}` × `fill_fraction ∈ {0.05, 0.125, 0.25}` ×
`gs_iters ∈ {0, 10, 40}`, record the reconstruction/target correlation at the
+1 order. Produce a table. Report the frontier, do not pick a winner.

**T3 — Diffraction efficiency budget.** Compute, end to end: LED optical
watts → ON-mirror fraction → first-order efficiency (ceiling 1/π² ≈ 10.1%) →
lumens reaching the reconstruction plane → whether it is visible on a matte
wall in a dark room. State the assumptions you add; there are several the
package does not fix for you.

**T4 — Diamond-lattice check.** `ogr.diagonal.diamond_positions` is marked
`[ASSERTED — VERIFY ON HARDWARE]`. Predict the diffraction-order pattern for
both the orthogonal and the centred-rectangular lattice model. They differ
observably. State the discriminating measurement.

**T5 — Two-DMD off-axis.** Model a DLP3010ULC producing a plane-wave
reference and a DLP4500 producing the object beam. Determine the reference
angle range, the required fringe pitch on the 3010, and the coherence budget.
Flag anything that fails.

---

## 5. Rules of engagement

- **Register tags are mandatory.** Every claim you add is tagged `[PROVED]`
  (arithmetic or formally verified), `[ASSERTED]` (standard physics with a
  citation, not proved here), or `[HEURISTIC]` (interpretive). An untagged
  claim is a defect.
- **Do not weaken a tolerance to make a test pass.** If a check fails, the
  claim is wrong. Report it.
- **Two baselines minimum for any new result.** A number with no comparison
  is not a result.
- **Pre-register before you sweep.** Write the expected outcome and the kill
  criterion into `docs/PREREGISTRATION.md` before running, not after.
- **Simulate before you build.** `pipeline.simulate(pattern)` gives the
  predicted intensity. Any bench photograph must be compared against it.
- **Do not claim hardware validation from a simulation.** The package
  contains zero measurements. Every physical number in it is a datasheet
  value or a derivation from one.

---

## 6. Known open items

- Coherence: an unfiltered LED gives fringe visibility below 0.3. A ~75 µm
  pinhole restores it at roughly 40× intensity cost. That trade is not
  resolved here and it is the main risk to a projector-only demonstration.
- Wall-bounce (`d_dmd_wall` → `d_wall_recon`) enlarges the geometric
  aperture but not the coherent one. Do not claim axial resolution from it.
- `ogr.nlos` shows the Lambertian transport operator is rank-deficient
  (measured: rank 9 of 16, condition number 2.6e16). The projection duality
  is exact algebra over a subspace you must characterise before promising
  anything.
