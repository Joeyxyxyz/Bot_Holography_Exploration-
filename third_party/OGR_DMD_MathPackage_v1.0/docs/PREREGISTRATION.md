# PRE-REGISTRATION — OGR DMD bench run

Filled in **before** any hardware run. Numbers below are predictions from
this package, not measurements. Package contains zero measurements.

Frozen at package build. Any change after a run is an amendment and must be
dated and justified in place, not overwritten.

---

## Hypothesis

**H1.** A DLP4500 displaying a Lee-encoded binary hologram with an embedded
Fresnel lens phase (`f = z`) produces a recognisable glyph at the +1 order in
a plane 500 mm from the DMD, without any external Fourier optic.

**H0 (null).** The reconstruction plane shows the zero-order projected image
of the binary pattern and no glyph, i.e. the DMD behaves as a projector, not
a hologram.

---

## Baselines — two are required, both must be run

**B1 — zero-order baseline.** Display the same pattern with the Fresnel lens
phase removed (`f = ∞`). Prediction: the glyph does **not** appear at the +1
order; the pattern projects as an image. Distinguishes hologram from
projection.

**B2 — scrambled-phase baseline.** Display a pattern encoding the same
amplitude with the Gerchberg–Saxton phase replaced by a fresh random draw.
Prediction: same ON fraction, same total flux, **no** glyph at the +1 order.
Distinguishes structure from brightness.

A positive result on H1 without both baselines run is not a result.

---

## Predictions (computed, λ = 638 nm, z = 0.5 m, `f_c = 0.125`)

| quantity | prediction | source |
|---|---|---|
| reconstruction FOV | 42.20 mm | `recon_field_of_view` |
| recon sample pitch (N = 1140) | 37.0 µm | `recon_pixel_pitch` |
| glyph lateral offset from DC | 5.27 mm | `lee.glyph_offset_metres` |
| lateral resolution | 46.3 µm | `fresnel.lateral_resolution` |
| axial resolution | 26.8 mm | `fresnel.axial_resolution` |
| first-order intensity efficiency | 10.13% ceiling | `lee.first_order_efficiency` |
| measured \|c_1\| at f_c = 0.125 | 0.3082 | `lee.measured_first_order` |
| simulated recon/target correlation | 0.9766 | `ogr.validate` end-to-end |
| Fresnel number at 0.5 m | 37.3 | `hardware.fresnel_number` |
| wall coherence radius (357 mm spot) | 1.09 µm | `Geometry.wall_coherence_radius` |

---

## Kill criteria — declared in advance

**K1.** `python3 -m ogr.validate` returns anything other than 31/31.
→ The package is wrong. Stop; fix the package before touching hardware.

**K2.** Measured glyph offset from DC differs from 5.27 mm by more than 20%.
→ The carrier / sampling model is wrong. Do not re-fit `f_c` to match; report.

**K3.** Simulated-vs-photographed intensity correlation < 0.5 at the +1 order
after alignment.
→ H1 not supported. Report as such. Do not iterate the encoding until it
passes and then report the passing run.

**K4.** B1 (no lens phase) also shows a glyph at the +1 order.
→ The observation is projection, not holographic reconstruction. H1 is not
tested by that run. Discard the run, not the null.

**K5.** B2 (scrambled phase) shows a glyph.
→ Something other than the encoded phase is producing the structure.
Diagnose before proceeding.

**K6.** Fringe visibility at the DMD plane, measured with a two-pinhole test
at the mirror pitch, < 0.3.
→ Coherence is insufficient. Pinhole required; re-run the flux budget before
claiming a projector-only result.

**K7.** Two-layer depth run: the two layers are separated by less than the
computed axial resolution for the actual aperture used.
→ The run cannot demonstrate depth separation regardless of what it looks
like. Redesign the ladder before running.

---

## What would count as a genuine positive

All of:

1. `ogr.validate` 31/31 before the run.
2. Glyph visible at the +1 order, offset within 20% of 5.27 mm.
3. B1 negative, B2 negative.
4. Photograph/simulation correlation ≥ 0.5 after alignment only (no
   re-encoding).
5. Fringe visibility ≥ 0.3 measured, not assumed.
6. Flux budget closed: measured plane brightness within one order of
   magnitude of the predicted 10.13%-ceiling budget.

Anything less is a partial result and is reported as one.

---

## Amendments

*(none — record any post-hoc change here with date and reason)*
