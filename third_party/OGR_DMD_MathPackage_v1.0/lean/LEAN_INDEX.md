# Lean sources — unmodified corpus copies

Pin: `leanprover/lean4:v4.24.0`, Mathlib `f897ebcf72cd16f89ab4577d0c826cd14afaafc7`.
These files are **not recompiled** by this package. The Python implementation
re-derives their numerical content independently; disagreements are recorded
in `../docs/CORRECTIONS.md`.

| file | content |
|---|---|
| `output56_signed_nullification.lean` | 4-class signed system, ±0.0e |
| `output57_signed_multiplicity.lean` | one-sidedness, signed multiplicity |
| `output86_pole_probe.lean` | leveling theorem, signed probes |
| `output87_dmd_projection.lean` | Z-depth emergence on the DLP4500 |
| `output88_cube_projection.lean` | pool accumulation, 3D cube, 4 strategies |
| `output89_nlos_projection_duality.lean` | NLoS projection = dual of reconstruction |
| `output90_ogr_projector_only.lean` | Fraunhofer, DMD as Fourier operator, coherence |
| `output91_ogr_wall_bounce_babinet_depth_ref.lean` | wall-bounce, Babinet, diagonal zero-line |
| `output92_signed_depth_multiplexing.lean` | ±0.0e dual volumetric layers |
| `output93_ogr_unified_synthesis.lean` | glyph + reference in one pattern |
| `output94_binary_hologram_two_dmd.lean` | Lee encoding, two-DMD off-axis |
| `aristotle_returns/` | Aristotle-processed versions of the same outputs |

## Known status

- Output 93 `depth_trichotomy` was **rejected by Aristotle** (two functionals).
  Output 94 repaired consistency but flipped the physical orientation.
  Correct repair: `../docs/LEAN_PATCH.md`.
- Output 90's Fraunhofer header figures are off by 10³ (metres read as
  millimetres). The theorem ordering `red < green` is unaffected and true.
- Run `#print axioms` on every guard theorem after any Aristotle pass.
  `Lean.ofReduceBool` means `native_decide` bypassed the kernel: reject.
