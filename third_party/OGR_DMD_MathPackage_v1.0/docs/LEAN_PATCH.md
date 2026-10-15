# LEAN PATCH — depth trichotomy (corrects outputs 93 §4 and 94 §1)

Pin: `leanprover/lean4:v4.24.0`, Mathlib `f897ebcf72cd16f89ab4577d0c826cd14afaafc7`.

## The defect

Output 93 defined `ReferenceLine` by `⟪DiagDir, w⟫ = 0` but `PosDepth` /
`NegDepth` by `⟪PerpDir, w⟫`. Two different functionals, so the three sets are
not a partition. Aristotle's rejection of `depth_trichotomy` was correct.

Output 94 restored consistency by moving all three to `⟪PerpDir, ·⟫`. That
compiles, but it makes the reference line `span{(1,1)}` — parallel to the
stripe. The Fourier transform of a stripe is supported *perpendicular* to it.

## The repair

One functional, and it must be the stripe direction.

```lean
noncomputable def DiagDir : EuclideanSpace ℝ (Fin 2) := ![1, 1]
noncomputable def PerpDir : EuclideanSpace ℝ (Fin 2) := ![1, -1]

theorem diag_perp_orthogonal : ⟪DiagDir, PerpDir⟫_ℝ = 0 := by
  simp [DiagDir, PerpDir, EuclideanSpace.inner_eq_star_dotProduct]
  ring

def ReferenceLine : Set (EuclideanSpace ℝ (Fin 2)) := { w | ⟪DiagDir, w⟫_ℝ = 0 }
def PosDepth      : Set (EuclideanSpace ℝ (Fin 2)) := { w | ⟪DiagDir, w⟫_ℝ > 0 }
def NegDepth      : Set (EuclideanSpace ℝ (Fin 2)) := { w | ⟪DiagDir, w⟫_ℝ < 0 }

theorem depth_trichotomy :
    ReferenceLine ∪ PosDepth ∪ NegDepth = Set.univ := by
  ext w
  simp only [ReferenceLine, PosDepth, NegDepth, Set.mem_union, Set.mem_setOf_eq,
             Set.mem_univ, iff_true]
  rcases lt_trichotomy (⟪DiagDir, w⟫_ℝ) 0 with h | h | h
  · exact Or.inr h
  · exact Or.inl (Or.inl h)
  · exact Or.inl (Or.inr h)

theorem depth_regions_disjoint :
    Disjoint ReferenceLine PosDepth ∧ Disjoint ReferenceLine NegDepth ∧
    Disjoint PosDepth NegDepth := by
  refine ⟨?_, ?_, ?_⟩ <;>
    rw [Set.disjoint_left] <;>
    intro w hw hw' <;>
    simp only [ReferenceLine, PosDepth, NegDepth, Set.mem_setOf_eq] at hw hw' <;>
    linarith

theorem reference_line_eq_span_perp :
    ReferenceLine = { w | ∃ t : ℝ, w = t • PerpDir } := by
  sorry  -- orthogonal complement of a line in ℝ²; discharge from
         -- Submodule.orthogonal or by explicit coordinates
```

`reference_line_eq_span_perp` is the one statement carrying real content
(the reference line is `span{(1,-1)}`, not `span{(1,1)}`). It is left as a
named `sorry` rather than closed by tactic search: this is exactly the
place where a closure engine will happily prove whichever orientation the
definitions hand it, so the guard theorem must be kernel-verified, never
`native_decide`-closed.

## Numerical pin

`ogr.diagonal.measure_line_direction` FFTs an actual (1,1) stripe and
recovers the principal axis of the transform's energy:

```
measured unit vector = (0.7071067811865475, -0.7071067811865475)
```

i.e. `span{(1,-1)}`. The orientation is settled empirically, not by
convention, so the Lean definitions have an external check.

## Audit after any Aristotle run

```
#print axioms depth_trichotomy
#print axioms depth_regions_disjoint
#print axioms reference_line_eq_span_perp
```

`Lean.ofReduceBool` appearing in any of these means `native_decide` bypassed
the kernel. Reject the run.
