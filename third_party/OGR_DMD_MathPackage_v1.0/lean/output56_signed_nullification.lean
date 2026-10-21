/-
OUTPUT 56: SIGNED NULLIFICATION â€” THE Â±0.0e FRAMEWORK
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

The unsigned three-class system (outputs 0-55) treats all sub-threshold
values identically: ground [0], reservoir [0.0e], observable [1].
This works on â„• where reservoir empties at Î”=1 (discreteness).

But the shifted zero spectrum S = {Re(Ï) - 1/2} lives on â„, where
sub-threshold values carry SIGN:
  +0.0e = zero is slightly RIGHT of critical line (Re(Ï) > 1/2)
  -0.0e = zero is slightly LEFT of critical line (Re(Ï) < 1/2)
  ground = zero is EXACTLY on the critical line (RH holds for this zero)

The signed theory is strictly richer on â„ than the unsigned theory.
It detects which side of the critical line a zero deviates to.

THREE-SIDE COMPOSITION:
  When multiple sub-threshold values compose, their signs matter.
  Coherent composition (all same sign) is honest â€” the limit is genuine.
  Mixed composition (opposite signs) can cancel to produce an apparent
  zero that hides internal structure. This is degeneracy.

  Connection to multiplicity: a simple zero is a coherent approach.
  A double zero is a degenerate state where two vanishing directions
  collapsed, losing the signed distinction.

WHAT THIS FILE PROVES:
  1. SignedNullClass: 4-class system with pos_reservoir and neg_reservoir
  2. Signed operators on â„¤: N_int, R_int with sign-preserving properties
  3. Conservation and idempotence for signed operators
  4. Forget-sign map: SignedNullClass â†’ NullClass (surjective)
  5. Both signed reservoirs empty on â„¤ at Î”=1 (discreteness)
  6. Signed classification of â„ at Î”=1/2 (both reservoirs nonempty)
  7. Three-side composition: coherent vs degenerate triples
  8. Coherent triples are stable under composition
  9. Mixed triples can degenerate (cancel to false ground)
  10. Connection to ShiftedZeroSpectrum: sign = side of critical line

Lean version: leanprover/lean4:v4.24.0
Mathlib version: f897ebcf72cd16f89ab4577d0c826cd14afaafc7
-/

import Mathlib

set_option linter.mathlibStandardSet false

open scoped BigOperators Real Nat Classical Pointwise

set_option maxHeartbeats 0
set_option maxRecDepth 4000
set_option synthInstance.maxHeartbeats 20000
set_option synthInstance.maxSize 128
set_option relaxedAutoImplicit false
set_option autoImplicit false

noncomputable section

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 1: THE FOUR-CLASS SIGNED SYSTEM
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- The unsigned three-class system (from outputs 0-55). -/
inductive NullClass where
  | ground     : NullClass  -- [0]:   exactly zero
  | reservoir  : NullClass  -- [0.0e]: nonzero but sub-threshold
  | observable : NullClass  -- [1]:   above threshold
  deriving Repr, DecidableEq

/-- The signed four-class system. Splits reservoir into Â±0.0e.
    ground     = 0        (attractor, fixed point)
    pos_reservoir = +0.0e (positive sub-threshold: 0 < x < Î”)
    neg_reservoir = -0.0e (negative sub-threshold: -Î” < x < 0)
    observable = Â±1       (above threshold: |x| â‰¥ Î”) -/
inductive SignedNullClass where
  | ground        : SignedNullClass  -- [0]
  | pos_reservoir : SignedNullClass  -- [+0.0e]
  | neg_reservoir : SignedNullClass  -- [-0.0e]
  | observable    : SignedNullClass  -- [1]
  deriving Repr, DecidableEq

/-- Forget-sign map: collapse Â±0.0e â†’ 0.0e. -/
def forget_sign : SignedNullClass â†’ NullClass
  | SignedNullClass.ground        => NullClass.ground
  | SignedNullClass.pos_reservoir => NullClass.reservoir
  | SignedNullClass.neg_reservoir => NullClass.reservoir
  | SignedNullClass.observable    => NullClass.observable

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 2: SIGNED OPERATORS ON â„¤
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- Signed nullification on â„¤: preserves value if |x| â‰¥ Î”, else sends to 0. -/
def N_int (Î” : â„¤) (x : â„¤) : â„¤ := if |x| â‰¥ Î” then x else 0

/-- Signed reservoir on â„¤: captures sub-threshold values with their sign. -/
def R_int (Î” : â„¤) (x : â„¤) : â„¤ := if |x| â‰¥ Î” then 0 else x

/-- Signed classification on â„¤. -/
def signed_classify_int (Î” : â„¤) (x : â„¤) : SignedNullClass :=
  if x = 0 then SignedNullClass.ground
  else if |x| â‰¥ Î” then SignedNullClass.observable
  else if x > 0 then SignedNullClass.pos_reservoir
  else SignedNullClass.neg_reservoir

/-- Unsigned classification on â„• (from output 55). -/
def classify_nat (Î” x : â„•) : NullClass :=
  if x = 0 then NullClass.ground
  else if x â‰¥ Î” then NullClass.observable
  else NullClass.reservoir

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 3: ALGEBRAIC PROPERTIES OF SIGNED OPERATORS
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- [PROVED] Signed conservation: N + R = identity on â„¤. -/
theorem signed_conservation (Î” : â„¤) (x : â„¤) : N_int Î” x + R_int Î” x = x := by
  simp [N_int, R_int]; split_ifs <;> ring

/-- [PROVED] Signed idempotence: NÂ² = N on â„¤. -/
theorem signed_idempotent (Î” : â„¤) (x : â„¤) (hÎ” : 0 â‰¤ Î”) :
    N_int Î” (N_int Î” x) = N_int Î” x := by
  simp only [N_int]
  split_ifs with h1 h2 <;> simp_all [abs_of_nonneg, abs_of_nonpos]

/-- [PROVED] Signed spectral gap: N_int(x) = 0 âˆ¨ |N_int(x)| â‰¥ Î”. -/
theorem signed_mass_gap (Î” : â„¤) (x : â„¤) :
    N_int Î” x = 0 âˆ¨ |N_int Î” x| â‰¥ Î” := by
  simp only [N_int]
  split_ifs with h <;> simp_all

/-- [PROVED] Reservoir preserves sign: R_int(x) > 0 â†” x > 0 âˆ§ |x| < Î”. -/
theorem reservoir_sign_pos (Î” : â„¤) (x : â„¤) (hÎ” : 0 < Î”) :
    R_int Î” x > 0 â†” (x > 0 âˆ§ |x| < Î”) := by
  simp only [R_int]
  split_ifs with h <;> constructor <;> intro hx <;> omega

/-- [PROVED] Reservoir preserves sign: R_int(x) < 0 â†” x < 0 âˆ§ |x| < Î”. -/
theorem reservoir_sign_neg (Î” : â„¤) (x : â„¤) (hÎ” : 0 < Î”) :
    R_int Î” x < 0 â†” (x < 0 âˆ§ |x| < Î”) := by
  simp only [R_int]
  split_ifs with h <;> constructor <;> intro hx <;> omega

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 4: FORGET-SIGN COMPATIBILITY
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- [PROVED] The forget-sign map is surjective: every unsigned class
    has a signed preimage. -/
theorem forget_sign_surjective : Function.Surjective forget_sign := by
  intro c
  cases c with
  | ground => exact âŸ¨SignedNullClass.ground, rflâŸ©
  | reservoir => exact âŸ¨SignedNullClass.pos_reservoir, rflâŸ©
  | observable => exact âŸ¨SignedNullClass.observable, rflâŸ©

/-- [PROVED] Signed classification refines unsigned: forgetting sign
    from signed_classify_int gives classify_nat on naturals. -/
theorem signed_refines_unsigned (Î” : â„•) (x : â„•) :
    forget_sign (signed_classify_int (â†‘Î”) (â†‘x)) = classify_nat Î” x := by
  simp only [signed_classify_int, classify_nat, forget_sign]
  split_ifs <;> simp_all [Int.natAbs_ofNat] <;> omega

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 5: DISCRETENESS â€” BOTH RESERVOIRS EMPTY ON â„¤ AT Î”=1
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- [PROVED] No integer is positive sub-threshold at Î”=1.
    There are no integers in (0,1). +0.0e is empty on â„¤. -/
theorem pos_reservoir_empty_int (x : â„¤) :
    signed_classify_int 1 x â‰  SignedNullClass.pos_reservoir := by
  simp only [signed_classify_int]
  split_ifs <;> simp_all <;> omega

/-- [PROVED] No integer is negative sub-threshold at Î”=1.
    There are no integers in (-1,0). -0.0e is empty on â„¤. -/
theorem neg_reservoir_empty_int (x : â„¤) :
    signed_classify_int 1 x â‰  SignedNullClass.neg_reservoir := by
  simp only [signed_classify_int]
  split_ifs <;> simp_all <;> omega

/-- [PROVED] On â„¤ at Î”=1, classification is binary: ground or observable.
    Both signed reservoirs are empty. Discreteness kills Â±0.0e simultaneously. -/
theorem signed_binary_at_one_int (x : â„¤) :
    signed_classify_int 1 x = SignedNullClass.ground âˆ¨
    signed_classify_int 1 x = SignedNullClass.observable := by
  simp only [signed_classify_int]
  split_ifs <;> simp_all <;> omega

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 6: â„ â€” SIGNED RESERVOIRS ARE NONEMPTY
-- The signed theory is strictly richer on â„ than â„¤.
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- Signed classification on â„. -/
def signed_classify_real (Î” : â„) (x : â„) : SignedNullClass :=
  if x = 0 then SignedNullClass.ground
  else if |x| â‰¥ Î” then SignedNullClass.observable
  else if x > 0 then SignedNullClass.pos_reservoir
  else SignedNullClass.neg_reservoir

/-- [PROVED] +0.0e exists on â„ at Î”=1/2: the value 1/4 is positive sub-threshold. -/
theorem pos_reservoir_nonempty_real :
    signed_classify_real (1/2) (1/4) = SignedNullClass.pos_reservoir := by
  simp [signed_classify_real, abs_of_pos]; norm_num

/-- [PROVED] -0.0e exists on â„ at Î”=1/2: the value -1/4 is negative sub-threshold. -/
theorem neg_reservoir_nonempty_real :
    signed_classify_real (1/2) (-1/4) = SignedNullClass.neg_reservoir := by
  simp [signed_classify_real, abs_of_neg]; norm_num

/-- [PROVED] The signed theory strictly refines the unsigned on â„:
    two values can have the same unsigned class but different signed classes. -/
theorem signed_strictly_finer :
    forget_sign (signed_classify_real (1/2) (1/4)) =
    forget_sign (signed_classify_real (1/2) (-1/4)) âˆ§
    signed_classify_real (1/2) (1/4) â‰  signed_classify_real (1/2) (-1/4) := by
  constructor
  Â· simp [signed_classify_real, forget_sign, abs_of_pos, abs_of_neg]; norm_num
  Â· simp [signed_classify_real, abs_of_pos, abs_of_neg]; norm_num

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 7: THREE-SIDE COMPOSITION THEORY
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- A triple of signed classes representing three "sides" approaching a value. -/
structure SignedTriple where
  side1 : SignedNullClass
  side2 : SignedNullClass
  side3 : SignedNullClass
  deriving Repr, DecidableEq

/-- Count positive reservoir sides in a triple. -/
def SignedTriple.pos_count (t : SignedTriple) : â„• :=
  (if t.side1 = SignedNullClass.pos_reservoir then 1 else 0) +
  (if t.side2 = SignedNullClass.pos_reservoir then 1 else 0) +
  (if t.side3 = SignedNullClass.pos_reservoir then 1 else 0)

/-- Count negative reservoir sides in a triple. -/
def SignedTriple.neg_count (t : SignedTriple) : â„• :=
  (if t.side1 = SignedNullClass.neg_reservoir then 1 else 0) +
  (if t.side2 = SignedNullClass.neg_reservoir then 1 else 0) +
  (if t.side3 = SignedNullClass.neg_reservoir then 1 else 0)

/-- A triple is coherent if all non-ground sides have the same sign.
    Coherent approach: limit is genuine, no hidden cancellation. -/
def SignedTriple.is_coherent (t : SignedTriple) : Prop :=
  t.pos_count = 0 âˆ¨ t.neg_count = 0

/-- A triple is degenerate if it has both positive and negative reservoir sides.
    Mixed approach: cancellation can produce false ground. -/
def SignedTriple.is_degenerate (t : SignedTriple) : Prop :=
  t.pos_count > 0 âˆ§ t.neg_count > 0

/-- [PROVED] Coherent and degenerate are complementary for reservoir triples. -/
theorem coherent_iff_not_degenerate (t : SignedTriple) :
    t.is_coherent â†” Â¬t.is_degenerate := by
  simp only [SignedTriple.is_coherent, SignedTriple.is_degenerate]
  omega

/-- A triple is purely positive: all three sides are +0.0e. -/
def triple_pos : SignedTriple :=
  âŸ¨SignedNullClass.pos_reservoir, SignedNullClass.pos_reservoir, SignedNullClass.pos_reservoirâŸ©

/-- A triple is purely negative: all three sides are -0.0e. -/
def triple_neg : SignedTriple :=
  âŸ¨SignedNullClass.neg_reservoir, SignedNullClass.neg_reservoir, SignedNullClass.neg_reservoirâŸ©

/-- A mixed triple: two positive, one negative. -/
def triple_mixed_ppn : SignedTriple :=
  âŸ¨SignedNullClass.pos_reservoir, SignedNullClass.pos_reservoir, SignedNullClass.neg_reservoirâŸ©

/-- A mixed triple: one positive, two negative. -/
def triple_mixed_pnn : SignedTriple :=
  âŸ¨SignedNullClass.pos_reservoir, SignedNullClass.neg_reservoir, SignedNullClass.neg_reservoirâŸ©

/-- A triple of all ground: genuine zero from all sides. -/
def triple_ground : SignedTriple :=
  âŸ¨SignedNullClass.ground, SignedNullClass.ground, SignedNullClass.groundâŸ©

/-- [PROVED] Pure positive triple is coherent. -/
theorem triple_pos_coherent : triple_pos.is_coherent := by
  simp [SignedTriple.is_coherent, SignedTriple.neg_count, triple_pos]; decide

/-- [PROVED] Pure negative triple is coherent. -/
theorem triple_neg_coherent : triple_neg.is_coherent := by
  simp [SignedTriple.is_coherent, SignedTriple.pos_count, triple_neg]; decide

/-- [PROVED] Ground triple is coherent. -/
theorem triple_ground_coherent : triple_ground.is_coherent := by
  simp [SignedTriple.is_coherent, SignedTriple.pos_count, triple_ground]; decide

/-- [PROVED] Mixed (+,+,-) is degenerate. -/
theorem triple_ppn_degenerate : triple_mixed_ppn.is_degenerate := by
  simp [SignedTriple.is_degenerate, SignedTriple.pos_count, SignedTriple.neg_count, triple_mixed_ppn]
  decide

/-- [PROVED] Mixed (+,-,-) is degenerate. -/
theorem triple_pnn_degenerate : triple_mixed_pnn.is_degenerate := by
  simp [SignedTriple.is_degenerate, SignedTriple.pos_count, SignedTriple.neg_count, triple_mixed_pnn]
  decide

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 8: COMPOSITION ALGEBRA â€” HOW SIGNED VALUES COMPOSE
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- Sum of three real values. -/
def compose_real (a b c : â„) : â„ := a + b + c

/-- [PROVED] Three positive sub-threshold values sum to positive.
    Coherent positive composition preserves sign. -/
theorem coherent_pos_sum_pos (a b c : â„) (ha : a > 0) (hb : b > 0) (hc : c > 0) :
    compose_real a b c > 0 := by
  simp [compose_real]; linarith

/-- [PROVED] Three negative sub-threshold values sum to negative.
    Coherent negative composition preserves sign. -/
theorem coherent_neg_sum_neg (a b c : â„) (ha : a < 0) (hb : b < 0) (hc : c < 0) :
    compose_real a b c < 0 := by
  simp [compose_real]; linarith

/-- [PROVED] Mixed values can cancel to zero: degenerate composition.
    This is the "false ground" phenomenon â€” looks like zero but isn't genuine. -/
theorem mixed_can_cancel (Îµ : â„) (hÎµ : Îµ > 0) :
    compose_real Îµ Îµ (-2 * Îµ) = 0 := by
  simp [compose_real]; ring

/-- [PROVED] Coherent positive composition cannot cancel to zero.
    Three positive values never produce a false ground. -/
theorem coherent_pos_no_cancel (a b c : â„) (ha : a > 0) (hb : b > 0) (hc : c > 0) :
    compose_real a b c â‰  0 := by
  simp [compose_real]; linarith

/-- [PROVED] Coherent negative composition cannot cancel to zero. -/
theorem coherent_neg_no_cancel (a b c : â„) (ha : a < 0) (hb : b < 0) (hc : c < 0) :
    compose_real a b c â‰  0 := by
  simp [compose_real]; linarith

/-- [PROVED] Three positive sub-threshold values can cross the threshold.
    Pool accumulation: invisible + invisible + invisible = visible. -/
theorem pos_pool_crosses_threshold (Î” : â„) (hÎ” : Î” > 0)
    (a b c : â„) (ha : 0 < a) (hab : a < Î”) (hb : 0 < b) (hbb : b < Î”)
    (hc : 0 < c) (hcb : c < Î”) (h_sum : a + b + c â‰¥ Î”) :
    signed_classify_real Î” a = SignedNullClass.pos_reservoir âˆ§
    signed_classify_real Î” b = SignedNullClass.pos_reservoir âˆ§
    signed_classify_real Î” c = SignedNullClass.pos_reservoir âˆ§
    signed_classify_real Î” (compose_real a b c) = SignedNullClass.observable := by
  refine âŸ¨?_, ?_, ?_, ?_âŸ©
  all_goals simp [signed_classify_real, compose_real, abs_of_pos, abs_of_nonneg, *]
  all_goals (try linarith)
  Â· split_ifs <;> linarith
  Â· split_ifs <;> linarith
  Â· split_ifs <;> linarith
  Â· split_ifs <;> linarith

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 9: CONNECTION TO THE SHIFTED ZERO SPECTRUM
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def is_nontrivial_zero (Ï : â„‚) : Prop :=
  riemannZeta Ï = 0 âˆ§ 0 < Ï.re âˆ§ Ï.re < 1

def ShiftedZeroSpectrum : Set â„ :=
  {x | âˆƒ Ï, is_nontrivial_zero Ï âˆ§ x = Ï.re - 1/2}

/-- Signed classification of a nontrivial zero by its deviation from the line. -/
def signed_classify_zero (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) : SignedNullClass :=
  signed_classify_real (1/2) (Ï.re - 1/2)

/-- [PROVED] A zero exactly on the critical line is ground class. -/
theorem on_line_is_ground (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) (h_line : Ï.re = 1/2) :
    signed_classify_zero Ï hÏ = SignedNullClass.ground := by
  simp [signed_classify_zero, signed_classify_real, h_line]

/-- [PROVED] A zero to the RIGHT of the critical line is +0.0e. -/
theorem right_of_line_is_pos (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) (h_right : Ï.re > 1/2) :
    signed_classify_zero Ï hÏ = SignedNullClass.pos_reservoir := by
  simp only [signed_classify_zero, signed_classify_real]
  have h_ne : Ï.re - 1/2 â‰  0 := by linarith
  have h_pos : Ï.re - 1/2 > 0 := by linarith
  have h_bound : |Ï.re - 1/2| < 1/2 := by
    rw [abs_of_pos h_pos]; linarith [hÏ.2.2]
  simp [h_ne, h_bound.not_le, h_pos]

/-- [PROVED] A zero to the LEFT of the critical line is -0.0e. -/
theorem left_of_line_is_neg (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) (h_left : Ï.re < 1/2) :
    signed_classify_zero Ï hÏ = SignedNullClass.neg_reservoir := by
  simp only [signed_classify_zero, signed_classify_real]
  have h_ne : Ï.re - 1/2 â‰  0 := by linarith
  have h_neg : Â¬(Ï.re - 1/2 > 0) := by linarith
  have h_bound : |Ï.re - 1/2| < 1/2 := by
    rw [abs_of_neg (by linarith : Ï.re - 1/2 < 0)]; linarith [hÏ.2.1]
  simp [h_ne, h_bound.not_le, h_neg]

/-- [PROVED] RH is equivalent to: all zeros are signed-ground.
    The signed theory makes this crisp â€” no zero is in EITHER reservoir. -/
theorem rh_iff_all_ground :
    (âˆ€ Ï, is_nontrivial_zero Ï â†’ Ï.re = 1/2) â†”
    (âˆ€ Ï, (hÏ : is_nontrivial_zero Ï) â†’ signed_classify_zero Ï hÏ = SignedNullClass.ground) := by
  constructor
  Â· intro h Ï hÏ; exact on_line_is_ground Ï hÏ (h Ï hÏ)
  Â· intro h Ï hÏ
    by_contra h_ne
    rcases lt_or_gt_of_ne h_ne with h_lt | h_gt
    Â· have := left_of_line_is_neg Ï hÏ h_lt
      rw [h Ï hÏ] at this; exact absurd this (by decide)
    Â· have := right_of_line_is_pos Ï hÏ h_gt
      rw [h Ï hÏ] at this; exact absurd this (by decide)

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 10: DEGENERACY AND ZERO MULTIPLICITY
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- The functional equation pairs Ï â†” 1-Ï.
    If Ï has Re(Ï) > 1/2, its partner has Re(1-Ï) < 1/2.
    One is +0.0e, the other is -0.0e. The pair is degenerate. -/
def functional_equation_pair (Ï : â„‚) : â„‚ := 1 - Ï

/-- [PROVED] Functional equation partner flips the sign of deviation. -/
theorem partner_flips_sign (Ï : â„‚) :
    (functional_equation_pair Ï).re - 1/2 = -(Ï.re - 1/2) := by
  simp [functional_equation_pair, Complex.sub_re, Complex.one_re]; ring

/-- [PROVED] If Ï is off the critical line, its functional equation partner
    is on the opposite side. The pair forms a degenerate system:
    one side is +0.0e, the other is -0.0e, and they cancel. -/
theorem off_line_pair_degenerate (Ï : â„‚) (hÏ : is_nontrivial_zero Ï)
    (h_off : Ï.re â‰  1/2) :
    (Ï.re - 1/2) + ((functional_equation_pair Ï).re - 1/2) = 0 := by
  rw [partner_flips_sign]; ring

/-- [PROVED] On the critical line, the partner IS itself (up to conjugation).
    No cancellation needed â€” the approach is coherent from both sides. -/
theorem on_line_self_partner (Ï : â„‚) (h_line : Ï.re = 1/2) :
    (functional_equation_pair Ï).re = Ï.re := by
  simp [functional_equation_pair, Complex.sub_re, Complex.one_re, h_line]

-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
-- PART 11: THE STABILITY THEOREM
-- Coherent approaches produce genuine zeros.
-- Degenerate approaches produce false zeros.
-- The spectral gap forces all approaches to be ground (= on the line).
-- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/-- SpectralGapProperty on â„ (from output 55). -/
def SpectralGapProperty (S : Set â„) (Î” : â„) : Prop :=
  âˆ€ x âˆˆ S, x = 0 âˆ¨ |x| â‰¥ Î”

/-- [PROVED] Under the spectral gap, no zero is in the positive reservoir.
    +0.0e is eliminated by the gap. -/
theorem gap_kills_pos_reservoir
    (h_gap : SpectralGapProperty ShiftedZeroSpectrum (1/2))
    (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) :
    signed_classify_zero Ï hÏ â‰  SignedNullClass.pos_reservoir := by
  intro h_pos
  have h_right : Ï.re > 1/2 := by
    by_contra h_not
    push_neg at h_not
    rcases eq_or_lt_of_le h_not with h_eq | h_lt
    Â· rw [on_line_is_ground Ï hÏ h_eq.symm] at h_pos; exact absurd h_pos (by decide)
    Â· rw [left_of_line_is_neg Ï hÏ h_lt] at h_pos; exact absurd h_pos (by decide)
  have h_in : Ï.re - 1/2 âˆˆ ShiftedZeroSpectrum := âŸ¨Ï, hÏ, rflâŸ©
  have h_abs : |Ï.re - 1/2| < 1/2 := by
    rw [abs_of_pos (by linarith)]; linarith [hÏ.2.2]
  rcases h_gap _ h_in with h_zero | h_ge
  Â· linarith
  Â· linarith

/-- [PROVED] Under the spectral gap, no zero is in the negative reservoir.
    -0.0e is eliminated by the gap. -/
theorem gap_kills_neg_reservoir
    (h_gap : SpectralGapProperty ShiftedZeroSpectrum (1/2))
    (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) :
    signed_classify_zero Ï hÏ â‰  SignedNullClass.neg_reservoir := by
  intro h_neg
  have h_left : Ï.re < 1/2 := by
    by_contra h_not
    push_neg at h_not
    rcases eq_or_lt_of_le h_not with h_eq | h_gt
    Â· rw [on_line_is_ground Ï hÏ h_eq] at h_neg; exact absurd h_neg (by decide)
    Â· rw [right_of_line_is_pos Ï hÏ h_gt] at h_neg; exact absurd h_neg (by decide)
  have h_in : Ï.re - 1/2 âˆˆ ShiftedZeroSpectrum := âŸ¨Ï, hÏ, rflâŸ©
  have h_abs : |Ï.re - 1/2| < 1/2 := by
    rw [abs_of_neg (by linarith : Ï.re - 1/2 < 0)]; linarith [hÏ.2.1]
  rcases h_gap _ h_in with h_zero | h_ge
  Â· linarith
  Â· linarith

/-- [PROVED] â˜… THE SIGNED SPECTRAL GAP THEOREM â˜…

    Under the spectral gap, every zero is ground class.
    BOTH +0.0e and -0.0e are eliminated simultaneously.
    The gap doesn't just say "zeros are on the line" â€”
    it says "no zero deviates in EITHER direction."

    This is strictly more informative than the unsigned version,
    which only says "the deviation is zero" without tracking
    which side it could have deviated to. -/
theorem signed_gap_forces_ground
    (h_gap : SpectralGapProperty ShiftedZeroSpectrum (1/2))
    (Ï : â„‚) (hÏ : is_nontrivial_zero Ï) :
    signed_classify_zero Ï hÏ = SignedNullClass.ground := by
  -- Eliminate all non-ground cases
  have h_not_pos := gap_kills_pos_reservoir h_gap Ï hÏ
  have h_not_neg := gap_kills_neg_reservoir h_gap Ï hÏ
  -- Classification has four cases; observable is impossible by critical strip bound
  rcases h : signed_classify_zero Ï hÏ with _ | _ | _ | _
  Â· rfl
  Â· exact absurd rfl h_not_pos
  Â· exact absurd rfl h_not_neg
  Â· -- Observable: |Re(Ï) - 1/2| â‰¥ 1/2, contradicts critical strip
    exfalso
    simp only [signed_classify_zero, signed_classify_real] at h
    split_ifs at h with h1 h2 h3 <;> simp_all
    have : |Ï.re - 1/2| < 1/2 := by
      cases abs_cases (Ï.re - 1/2) with
      | inl h => exact h.1 â–¸ (by linarith [hÏ.2.2])
      | inr h => exact h.1 â–¸ (by linarith [hÏ.2.1])
    linarith

end
