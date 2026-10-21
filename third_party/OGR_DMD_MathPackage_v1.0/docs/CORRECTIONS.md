# CORRECTIONS TO OUTPUTS 87–94

Five defects found while making the corpus executable. Listed by severity.
Each has the wrong statement, the correct statement, the evidence, and what
it costs.

None of these touch the Lean *theorems*, which are consistent with their own
definitions. Four are in header prose and physical interpretation; one
(C3) is a definitional inconsistency that Aristotle had already flagged.

---

## C1 — Fraunhofer distance is in metres. Severity: high.

**Where.** Output 90 header, "PHYSICS" block; propagated to output 93's
`fraunhofer_threshold` commentary.

**Wrong.**
> For green λ = 528 nm: z >> 6.89e-3² / 528e-9 ≈ 90 mm
> At z = 500 mm we are solidly in Fraunhofer regime.
>
> fraunhofer_condition_red: z = 500mm >> 55mm ✓

**Correct.** `(6.89472e-3)² / 528e-9 = 90.03` — **metres**. Red short axis
74.51 m; red long axis 116.42 m; green long axis 140.68 m. The "55 mm" red
figure does not correspond to any aperture convention and appears to be a
separate slip.

**Evidence.** Fresnel number at z = 0.5 m, half-aperture 3.447 mm,
λ = 638 nm: `N_F = a²/(λz) = 37.3`. Far field requires `N_F ≪ 1`.
Reproduce: `ogr.hardware.DLP4500.fresnel_number(638e-9, 0.5)`.

**What survives.** Output 93's theorem `red_easier_fraunhofer`
(red threshold < green threshold) is **true** — 74.51 < 90.03. The ordering
is right; only the magnitude and the "we are in the far field" conclusion
are wrong.

**What it costs.** The projector-only claim as stated does not hold at 500 mm
with the full aperture. Three fixes, in order of preference:

1. Encode a Fresnel lens phase into the pattern (`f = z`). Cancels the chirp
   exactly — verified residual **1.4e-17**. Keeps "no external optics".
   **This is the package default.**
2. Add one Fourier-transforming lens; observe the back focal plane.
3. Use a 47×47-mirror sub-aperture (0.21% of the array). Not recommended.

---

## C2 — Depth is a quadratic phase, not a signed carrier. Severity: high.

**Where.** Output 92, Claims A–E; carried into output 93 §5.

**Wrong.** M⁺ and M⁻ given opposite-sign carriers, quoted as reconstructing at
`d_pos = λ_r · f_sampling / (2 sin θ⁺)`.

**Two failures.**

1. *Dimensions.* `λ [m] · f_sampling [1/m]` is dimensionless; dividing by
   `sin θ` leaves it dimensionless. It cannot be a distance.
2. *Mechanism.* A linear phase ramp **translates**. Opposite carriers put two
   glyphs left and right of DC **in the same plane**. That is lateral
   separation, not axial.

**Correct.** Axial placement requires a quadratic phase,
`L(x,y;f) = exp(-iπ(x²+y²)/(λf))`, applied per layer before summing. `+f`
real image in front, `−f` virtual behind, `f → ∞` nominal plane. Implemented
as `ogr.fresnel.lens_phase` / `encode_layers`.

**What survives.** The ± carrier remains correct and useful for **lateral**
order separation, and the signed-sign correspondence is preserved — it just
attaches to the sign of the quadratic term rather than the linear one. The
`[HEURISTIC]` mapping `+0.0e ↔` converging, `−0.0e ↔` diverging,
`[0] ↔` no curvature is cleaner under the correction than before it.

**New hard constraint this exposes.** Axial resolution
`δz = 2λ/NA² = 26.8 mm` at z = 0.5 m with the DMD's own aperture. Layers
closer than that are not resolvable, whatever the encoding. Output 88's depth
ladder (near 152 mm / mid 1296 mm / far 2440 mm) clears this comfortably.

---

## C3 — Depth trichotomy needs one functional. Severity: medium.

**Where.** Output 93 §4 (rejected by Aristotle); output 94 §1 (repair).

**Wrong (93).** `ReferenceLine` defined by `⟨DiagDir, w⟩ = 0` while
`PosDepth`/`NegDepth` used `⟨PerpDir, w⟩`. Two different functionals, so the
three sets are not a partition. Aristotle's rejection was correct.

**Incomplete repair (94).** All three moved to `⟨PerpDir, ·⟩`. Now internally
consistent, but it makes the reference line `span{(1,1)}` — *parallel* to the
stripe. The transform does not do that.

**Correct.** Use `⟨DiagDir, ·⟩` for all three:

```
ReferenceLine := { w | ⟨DiagDir, w⟩ = 0 }     -- = span{(1,-1)}
PosDepth      := { w | ⟨DiagDir, w⟩ > 0 }
NegDepth      := { w | ⟨DiagDir, w⟩ < 0 }
```

**Evidence.** A stripe constant along **d** and narrow along **n** is
separable, so `F[A]` is supported on `{w : ⟨d,w⟩ = 0}`. Measured principal
axis of the transform of a (1,1) stripe: **(0.7071, −0.7071)**. Reproduce:
`ogr.diagonal.measure_line_direction`.

Lean patch in `docs/LEAN_PATCH.md`.

---

## C4 — Encode the hologram, not the image. Severity: medium.

**Where.** Implicit throughout 90/93/94. Output 90's `encoding_exists` and
`F[F⁻¹[g]] = g` state it correctly; the pipeline prose does not make it
operational.

**Wrong in practice.** Lee-encoding the glyph bitmap directly reconstructs the
glyph's *transform*, not the glyph.

**Correct.** Encode `H = F⁻¹[glyph]`, with a random phase imposed on the
target amplitude (or Gerchberg–Saxton). Without a phase, energy piles into DC
and the reconstruction is one bright dot.

**Evidence.** With GS (40 iterations) at `fill = f_c = 0.125`,
reconstruction/target correlation = **0.9766**.

---

## C5 — Off-axis needs headroom; "1/4 of Nyquist" must be read carefully.
Severity: low-medium.

**Where.** Output 94 §2–3.

**Two items.**

1. Output 94 writes `f_c` as "typically 1/4 of Nyquist" = **0.125**
   cycles/mirror. Reading it as 0.25 costs **11.6%** first-order amplitude to
   carrier undersampling (4 samples/period). Measured table in
   `docs/MATH_SPEC.md` §5.
2. The stated criterion `f_c ≥ 1.5·B_glyph` is right but not operational.
   In grid terms it becomes **`fill_fraction ≤ 1.33·f_c`**, and the boundary
   is sharp:

   | fill | correlation |
   |---|---|
   | 0.50 | −0.0003 |
   | 0.25 | −0.0003 |
   | 0.125 | **0.9766** |

   The package raises `ValueError` above the bound rather than silently
   producing noise.

---

## Not corrected — flagged as open

- **Coherence budget.** Unfiltered LED gives visibility < 0.3; a ~75 µm
  pinhole restores it at ~40× intensity cost. Output 90 states both and does
  not resolve the trade. Still unresolved. Main risk to a projector-only
  demonstration.
- **"Burst coherence".** Output 90 correctly computes `τ_max = 80 fs` for the
  red LED and concludes the temporal route is unreachable by electronics,
  then reinterprets the mechanism as spatial. That reinterpretation is
  `[HEURISTIC]` and is not load-bearing anywhere in this package.
- **Diamond lattice geometry.** Modelled as centred-rectangular. Marked
  `[ASSERTED — VERIFY ON HARDWARE]`. Discriminating observable: the projected
  diffraction-order pattern.
- **Wall-bounce coherence gain.** Output 91 Claim A (i)/(iii) asserts wall
  scattering increases effective spatial coherence. A Lambertian surface
  *reduces* coherence; what the wall does supply is a larger secondary source
  and a van Cittert–Zernike coherence radius at the observation plane
  (`Geometry.wall_coherence_radius`). Computed for the stated geometry —
  357 mm wall spot (throw ratio 1.4 at 500 mm), 500 mm to the reconstruction
  plane — that radius is **1.09 µm** (red) / **0.90 µm** (green), i.e. about
  **1/7 of the DMD pitch**. Output 91 quotes ≈ 6.4 µm by assuming a 50 mm
  wall spot, which the throw ratio does not give at 500 mm. Under the stated
  geometry the coherence radius is well *below* the pitch, so wall-bounce as
  specified degrades rather than restores usable coherence. Either stop the
  wall spot down to ~50 mm (recovering ≈ 7.8 µm, comparable to the pitch) or
  drop the wall stage. This is a different mechanism from the one claimed and
  the net sign of the effect is unfavourable as written.
- **Two-DMD shared-LED coherence.** Open.
