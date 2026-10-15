# OGR MATH SPECIFICATION v1.0

Consolidates Messina Nullification Framework corpus outputs **87–94** into one
executable specification. Every statement carries a register tag:

- `[PROVED]` — arithmetic, or formally verified in Lean 4 (Mathlib f897ebcf),
  or numerically exact to machine precision in `ogr.validate`
- `[ASSERTED]` — standard physics with a source; not proved here
- `[HEURISTIC]` — interpretive mapping between the optics and the MNF operator
  algebra; carries no independent evidential weight

---

## 1. Hardware

`[ASSERTED — TI DLPU011E]`

| | DLP4500 | DLP3010ULC |
|---|---|---|
| array | 912 × 1140 | 1280 × 720 |
| pitch | 7.56 µm | 5.4 µm |
| tilt | ±12° | ±17° |
| lattice | diamond, smooth axis 45° | orthogonal, smooth axis 0° |
| 1-bit rate | 4225 Hz (min exposure 235 µs) | 4225 Hz |
| 8-bit rate | 120 Hz | 120 Hz |

`[PROVED]` Mirror count 912 × 1140 = **1,039,680**.
`[PROVED]` Short-axis aperture 912 × 7.56 µm = **6.89472 mm**.
`[PROVED]` Long-axis aperture 1140 × 7.56 µm = **8.6184 mm**.

Sources: red LED 638 nm (spatial coherence ≈ 24 µm), green 528 nm (≈ 5.8 µm),
blue 460 nm. `[ASSERTED — HPLED spatial coherence, ResearchGate 2012]`
`[PROVED]` Red coherence > green coherence, so red is preferred for OGR.

---

## 2. The reconstruction operator

`[ASSERTED — Goodman, Fourier Optics]` Fraunhofer diffraction:

```
U(x,y;z) = (e^{ikz}/(iλz)) · e^{ik(x²+y²)/2z} · F[t(u,v)]|_(x/λz, y/λz)
```

`[PROVED]` DFT correspondence, N samples of pitch p:

```
recon sample spacing   Δx  = λz/(Np)
reconstruction window  FOV = λz/p
angular FOV                = λ/p  =  one grating-order separation
```

The last equality is exact and not a coincidence: the DFT window *is* one
diffraction order. At λ = 638 nm, z = 0.5 m, p = 7.56 µm the FOV is
**42.2 mm**, i.e. ±2.42°.

`[PROVED]` `F^-1[F[t]] = t`. Lean: `Continuous.fourier_inversion_inv`
(output 90/93). Numerical residual 6.7e-16.

### 2.1 Validity — the correction

`[PROVED]` Fresnel number `N_F = a²/(λz)` with `a` the half-aperture.

```
DLP4500 half-aperture 3.447 mm, λ = 638 nm, z = 0.5 m  →  N_F = 37.3
```

`N_F ≫ 1` is the **near field**. Fraunhofer onset (`a²/λ` with the full
aperture) is **74.5 m** (red, short axis) / **116.4 m** (red, long axis) /
**90.0 m** (green, short axis) — *metres*, not millimetres. Output 90's
header records these as millimetres and concludes "at z = 500 mm we are
solidly in Fraunhofer regime". That conclusion is false by 10³.

`[PROVED]` Largest half-aperture genuinely in the far field at 0.5 m
(tolerance N_F ≤ 0.1): `a = √(0.1·λ·z) = 179 µm`, i.e. **47 mirrors across**,
0.21% of the array.

Three ways out:

1. **Encode the lens** — multiply the hologram by `exp(-iπr²/(λf))` with
   `f = z`. This cancels the Fresnel chirp exactly (`ogr.validate` residual
   1.4e-17), so the plain DFT becomes the correct operator and the
   projector-only claim survives. **Package default.**
2. **Physical Fourier lens** — the back focal plane is the exact transform
   plane at any distance. Cheapest bench fix.
3. **Sub-aperture** — use 47×47 mirrors. Loses 99.8% of the array and all
   resolution. Not recommended; listed for completeness.

`[ASSERTED]` Single-FFT Fresnel transform (`ogr.fourier.fresnel_reconstruct`):

```
U(x,y;z) ∝ F[ t(u,v) · exp(+iπ(u²+v²)/(λz)) ]
```

Sampling formulas above are unchanged; only the operator changes.

---

## 3. Babinet complementarity — conservation

`[PROVED]` For binary `t`, `t_OFF = 1 − t_ON`, hence

```
F[t_ON] + F[t_OFF] = F[1] = N_total · δ(f)
```

Numerical residual exactly 0.0 (float64, 256×256). Lean: `babinet_identity`
(output 91), `babinet93` (output 93).

`[HEURISTIC]` MNF reading: `N + R = identity` ↔ `F[ON] + F[OFF] = F[full]`,
with ON mirrors the `N` branch (glyph) and OFF mirrors the `R` branch
(reservoir / reference).

`[ASSERTED — caveat]` Physical Babinet holds for the **field leaving the
array**. OFF mirrors send light to the dump, so the wall records `|F[ON]|²`
alone. The "reference costs nothing" claim survives because the reference
stripe is built from mirrors already OFF inside the pattern support — not
because dumped light reappears.

---

## 4. Diagonal zero-line reference

`[PROVED]` A stripe constant along unit direction **d** and narrow along its
normal **n** is separable, `A(x) = g(⟨x,n⟩)·1(⟨x,d⟩)`, so

```
F[A](w) = G(⟨w,n⟩) · δ(⟨w,d⟩)      supported on { w : ⟨d, w⟩ = 0 }
```

Stripe along **(1,1)** → reconstruction line along **(1,−1)**. Measured
principal axis: (0.7071, −0.7071). The defining functional is `⟨DiagDir, ·⟩`.

`[PROVED]` Depth trichotomy, corrected:

```
ReferenceLine := { w | ⟨DiagDir, w⟩ = 0 }
PosDepth      := { w | ⟨DiagDir, w⟩ > 0 }
NegDepth      := { w | ⟨DiagDir, w⟩ < 0 }
```

One functional, three regions, partition verified. Output 93 mixed two
functionals (which is why Aristotle rejected its trichotomy); output 94
restored consistency but under `PerpDir`, which flips the physical
orientation. See `docs/LEAN_PATCH.md`.

`[ASSERTED — VERIFY]` Diamond lattice: modelled as centred-rectangular, odd
rows offset by half a pitch. The discriminating observable is the projected
diffraction-order pattern (square grid vs 45°-rotated grid with half-order
extinctions). Photograph before trusting absolute order positions.

---

## 5. Binary hologram encoding (Lee)

`[PROVED]` Encoding rule:

```
B(u,v) = 1  iff  cos(2π f_c u + φ(u,v)) ≥ cos(π A(u,v)),   A ∈ [0,1]
```

`B` is the indicator of an arc of angular width `2πA` centred at `−φ`, so its
carrier-harmonic coefficients are

```
c_m = e^{imφ} · sin(mπA) / (mπ)
c_1 = (1/π) · sin(πA) · e^{iφ}
```

Consequences:

- `[PROVED]` phase recovered exactly
- `[PROVED]` amplitude recovered as `sin(πA)/π`, **not** `A`. Pre-compensate
  with `A_enc = arcsin(A)/π`; then `c_1 = A/π` exactly (residual 0.0).
- `[PROVED]` peak first-order intensity efficiency `1/π² = 10.13%` at
  `A = 1/2`. This is a ceiling, not a target. Output 94's "F[B] at f_c
  exactly recovers H" is true only up to this factor and only in the +1 order.
- `[PROVED]` even harmonics vanish only at `A = 1/2`; general `A` leaves an
  `m = 2` ghost of magnitude `sin(2πA)/(2π)` at `2f_c`.

`[PROVED]` Carrier sampling. The closed form is the continuous limit; on a
sampled grid:

| f_c | samples/period | measured \|c_1\| | error |
|---|---|---|---|
| 0.250 | 4 | 0.2813 | −11.6% |
| 0.125 | 8 | 0.3082 | −3.2% |
| 0.0625 | 16 | 0.3158 | −0.8% |
| 0.03125 | 32 | 0.3177 | −0.2% |
| — | ∞ | 0.3183 | — |

Package default `f_c = 0.125` = one quarter of Nyquist, matching output 94's
text.

`[ASSERTED]` Off-axis separation: `f_c ≥ 1.5·B_glyph`, `f_c ≤ 0.5`.
`[PROVED]` Glyph lateral offset `x = f_c·λz/p = f_c·FOV`. At `f_c = 0.125`,
z = 0.5 m, red: **5.27 mm** off centre.

`[PROVED]` **Fill-fraction constraint** — measured, and it is sharp. The DC
autocorrelation term has half-width equal to the glyph half-width `W`;
non-overlap needs `f_c·N ≥ 1.5W`, i.e. `fill_fraction ≤ 1.33·f_c`.

| fill fraction | recon/target correlation |
|---|---|
| 0.500 | −0.0003 |
| 0.250 | −0.0003 |
| 0.125 | **0.9766** |

---

## 6. Encoding the hologram, not the image

`[PROVED]` Reconstruction is `F[pattern]`; to make it look like the glyph,
encode `H = F^-1[glyph]`. Impose a random phase on the target amplitude
first, or run Gerchberg–Saxton, otherwise all energy piles into DC and the
reconstruction is one bright dot.

End-to-end measured: `fill = 0.125`, `f_c = 0.125`, 40 GS iterations →
**correlation 0.9766** between the +1 order and the target.

---

## 7. Axial depth

`[ASSERTED — standard Fourier optics]` A **linear** phase ramp translates
laterally. A **quadratic** phase refocuses axially:

```
L(x,y;f) = exp(-iπ(x²+y²)/(λf))
```

- `f > 0` → converging → real image in front — `[HEURISTIC]` the `+0.0e` layer
- `f < 0` → diverging → virtual image behind — `[HEURISTIC]` the `−0.0e` layer
- `f → ∞` → no curvature → nominal plane — `[HEURISTIC]` the `[0]` ground

`[PROVED]` This is the correction to outputs 92/93, which use opposite-sign
**carriers** for depth. Opposite carriers place two glyphs left and right of
DC **in the same plane**. Output 92's quoted `d_pos = λ·f_sampling/(2 sin θ)`
is additionally dimensionless and cannot be a distance.

`[ASSERTED]` Resolution limits, `NA = a_coh/(2z)`:

```
lateral  δx = λ/(2NA) = λz/a_coh        =  46.3 µm
axial    δz = 2λ/NA²                    =  26.8 mm
```

at λ = 638 nm, z = 0.5 m, `a_coh` = 6.89 mm (DMD active area). **Depth layers
closer than ~27 mm are not resolvable.** `a_coh` is the *coherent* aperture;
wall-bounce enlarges the geometric aperture only.

`[ASSERTED]` Angular-spectrum propagation is used for validation; evanescent
components (`1 − (λf_x)² − (λf_y)² < 0`) are zeroed. `[HEURISTIC]` Those
components are the optical `[0.0e]` reservoir: present in the aperture,
contributing nothing observable at `z > 0`.

---

## 8. Signed mirror groups and pooling

`[PROVED]` `M⁺ = {j − i > w/2}`, `M⁻ = {j − i < −w/2}`, `M⁰ = {|j − i| ≤ w/2}`
partition the array; pairwise intersections empty. No mirror is simultaneously
`+0.0e` and `−0.0e`.

**This is a set-theoretic fact about a partition.** It is true and cheap. It
is *not* evidence that the two depth layers cannot interfere — that stronger
claim needs the axial-resolution argument in §7.

`[PROVED]` Pool accumulation: `0.4 + 0.4 + 0.4 = 1.2 ≥ 1.0` with each term
below threshold — three `[0.0e]` contributions pool to an observable `[1]`.

`[ASSERTED]` Physical caveat: PWM pooling is **incoherent intensity addition
over time**. It reaches visibility; it does not synthesise a coherent field.

`[PROVED]` Flicker gate: 3 frames at 4225 Hz = 0.71 ms ≪ 16.7 ms, so a pooled
set fuses to a steady percept. Any "invisible parts pool to a visible whole"
demonstration intended for the eye must clear this.

---

## 9. NLoS projection duality

`[PROVED]` Hadamard: `H_n H_nᵀ = 2ⁿ I`, `H⁻¹ = Hᵀ/2ⁿ`. Residual 0.0.

`[ASSERTED]` Lambertian transport `H[s,w] = ρ cos θ_i cos θ_o / (π r²)`.

`[PROVED]` The algebra of the duality is exact: reconstruction solves
`φ = H⁻¹ψ` for measured `ψ`, projection solves the same equation for chosen
`ψ`. Round-trip error for `ψ` in the range of `H`: **1.7e-08**.

`[PROVED]` The physics is not symmetric, and this is the finding:

- measured condition number **2.6e16**, numerical rank **9 of 16**
- dynamic range required **54.5 bits**; DMD provides **8**
- arbitrary `ψ` relative error **0.48** — most target fields are unreachable
- `φ` must be non-negative and bounded; `H⁻¹ψ` is signed in general, so a
  physical solve is constrained (`ogr.nlos.solve_nonneg`), not an inverse

The deliverable is a conditioning number and a constrained solve, not an
inverse.

---

## 10. Two-DMD off-axis architecture

`[ASSERTED — output 94]` DLP3010ULC (orthogonal lattice, clean horizontal
fringes, 5.4 µm pitch) generates the plane-wave reference; DLP4500 (diamond
lattice, 45° smooth axis) carries the Lee-encoded object beam. Both from one
LED. Interference at the relay wall gives off-axis holography with no beam
splitter and no laser.

`[PROVED]` 3010 pitch < 4500 pitch, so it does give finer angular control of
the reference direction.

`[ASSERTED — unresolved]` The coherence budget for a shared LED across two
separate optical paths is not settled in this package. Treat as open.

---

## Provenance

Corpus outputs consolidated: 87 (Z-depth emergence), 88 (cube / pool
accumulation), 89 (NLoS duality), 90 (projector-only), 91 (wall-bounce,
Babinet, diagonal reference), 92 (signed depth multiplexing), 93 (unified
synthesis), 94 (Lee encoding, two-DMD).

Lean 4 sources are in `lean/`, pinned at `leanprover/lean4:v4.24.0`,
Mathlib `f897ebcf72cd16f89ab4577d0c826cd14afaafc7`. This package does not
recompile them; it re-derives their numerical content independently and
reports where the two disagree (`docs/CORRECTIONS.md`).
