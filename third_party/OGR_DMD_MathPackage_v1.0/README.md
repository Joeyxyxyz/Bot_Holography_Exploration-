# OGR DMD Math Package v1.0

Executable mathematics for **Operation Glyph Retrieval** — holographic glyph
projection from a TI DLP digital micromirror device.

Consolidates Messina Nullification Framework corpus outputs **87–94** into one
numerically validated Python package, with five corrections to the source
material recorded in `docs/CORRECTIONS.md`.

## Quick start

```bash
python3 -m ogr.validate        # expect: 31/31 checks passed
python3 examples/make_patterns.py
```

Python 3.9+, NumPy. Nothing else. No network, no Pillow, no SciPy.

## Layout

```
AGENT_BRIEF.md              read this first if you are a coding agent
README.md                   this file
docs/MATH_SPEC.md           the full specification, register-tagged
docs/CORRECTIONS.md         five defects found in outputs 87–94
docs/PREREGISTRATION.md     baselines and kill criteria, frozen
docs/LEAN_PATCH.md          depth-trichotomy repair for outputs 93/94
ogr/                        the implementation (11 modules)
tests/                      standalone test runner, pytest-compatible
params/ogr_params.json      every constant, machine-readable
examples/                   runnable end-to-end scripts
lean/                       source Lean 4 files, unmodified
MANIFEST.sha256             integrity record
```

## Headline numbers (λ = 638 nm, z = 0.5 m, f_c = 0.125)

| | |
|---|---|
| reconstruction FOV | 42.20 mm |
| recon sample pitch (N = 1140) | 37.0 µm |
| glyph offset from DC | 5.27 mm |
| lateral resolution | 46.3 µm |
| **axial resolution** | **26.8 mm** |
| first-order efficiency ceiling | 10.13% |
| Fresnel number at 0.5 m | **37.3 (near field)** |
| end-to-end recon/target correlation | **0.9766** |

## Status

Zero measurements. Every physical number here is a datasheet value or a
derivation from one. Simulation only. See `docs/PREREGISTRATION.md` before
any bench run.

Register tags: `[PROVED]`, `[ASSERTED]`, `[HEURISTIC]`. Untagged claims are
defects.

MIT / CC-BY. Joey Messina.
