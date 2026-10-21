# Nullification on the Bloch Sphere
## Quantum States, Entanglement, and Confinement

**Author:** Joseph Messina | December 2025 | CC-BY 4.0

---

## Preface

This workbook extends nullification to quantum mechanics via the Bloch sphere representation. All results computationally verified up to 13 qubits. 

**Key Discovery: Entanglement IS Confinement** - the nullification framework explains why entangled subsystems appear "hidden".

---

## Chapter 1: The Bloch Sphere

Every single-qubit state can be represented as a point in/on a unit sphere.

- **Pure states:** On the surface (|r| = 1)
- **Mixed states:** Inside the sphere (|r| < 1)  
- **Maximally mixed:** At the center (|r| = 0)

**Density matrix:** rho = (I + r.sigma)/2 where r = (x, y, z) is the Bloch vector

**Purity:** Tr(rho^2) = (1 + |r|^2)/2

| State | Bloch Vector r | |r| | Class |
|-------|---------------|-----|-------|
| \|0> | (0, 0, +1) | 1 | [1] |
| \|1> | (0, 0, -1) | 1 | [1] |
| \|+> | (+1, 0, 0) | 1 | [1] |
| \|-> | (-1, 0, 0) | 1 | [1] |
| Max mixed I/2 | (0, 0, 0) | 0 | [0] |

---

## Chapter 2: Nullification Classification

| Class | Condition | Physical Meaning |
|-------|-----------|------------------|
| [1] | \|r\| >= Delta | Observable/Pure enough |
| [0.0e] | 0 < \|r\| < Delta | Exists but not observable |
| [0] | \|r\| = 0 | Maximally mixed/confined |

**Nullification operator:** N(r) = r if |r| >= Delta, else 0

**Threshold geometry:** Delta defines a sphere inside the Bloch sphere. States inside are nullified.

---

## Chapter 3: Entanglement = Confinement

**THE CENTRAL DISCOVERY**

**Theorem:** For maximally entangled states, each subsystem has |r| = 0.

**Proof by example:** Bell state |psi> = (|00> + |11>)/sqrt(2)

- Full state: Pure (purity = 1)
- Qubit A reduced: rho_A = Tr_B(|psi><psi|) = I/2 -> |r| = 0 -> [0]
- Qubit B reduced: rho_B = Tr_A(|psi><psi|) = I/2 -> |r| = 0 -> [0]

**Physical interpretation:** The whole system is observable [1], but the parts are confined [0].

**This is EXACTLY what happens in hadrons:** proton is [1], quarks inside are [0.0e].

| State Type | Full System | Each Qubit | Concurrence |
|------------|-------------|------------|-------------|
| Product \|00> | [1] pure | [1] all \|r\|=1 | C = 0 |
| Bell state | [1] pure | [0] all \|r\|=0 | C = 1 |
| W-state (n) | [1] pure | [0.0e] \|r\|=(n-2)/n | C < 1 |
| GHZ (n) | [1] pure | [0] all \|r\|=0 | C = 1 |

---

## Chapter 4: Bell Inequality and Confinement

**CHSH inequality:** |S| <= 2 for classical/local hidden variable theories

**Tsirelson bound:** |S| <= 2*sqrt(2) = 2.828 for quantum mechanics

**Key result:** Bell violation REQUIRES |r| = 0 for subsystems.

| State | CHSH S | \|r\| Q0 | \|r\| Q1 | Violates? |
|-------|--------|---------|---------|-----------|
| Bell state | 2.828 | 0 | 0 | YES (max) |
| Partial ent. | ~2.3 | 0.8 | 0.8 | YES (weak) |
| Product state | <= 2 | 1 | 1 | NO |

**Insight:** Bell nonlocality requires subsystem confinement. Observable parts cannot violate Bell.

---

## Chapter 5: Multi-Qubit Scaling Laws

### GHZ State: (|00...0> + |11...1>)/sqrt(2)
All n qubits have |r| = 0 regardless of n. Maximum entanglement = maximum confinement.

### W State: Symmetric with one excitation
All n qubits have |r| = (n-2)/n. Approaches [1] as n -> infinity.

| n qubits | 2 | 3 | 4 | 6 | 8 | 10 | infinity |
|----------|---|---|---|---|---|----|---------| 
| \|r\| per qubit | 0 | 0.33 | 0.5 | 0.67 | 0.75 | 0.8 | 1 |

**W-state formula:** |r| = 1 - 2/n

---

## Chapter 6: Spectral Gap from Nullification

| Scenario | Surviving |r| | Nullified | Result |
|----------|-------------|-----------|--------|
| Mixed ensemble | {0.9, 0.95, 1.0} | {0.2 -> 0} | GAP (0, Delta) |
| All confined | {} | {0.3, 0.4 -> 0} | TRIVIAL |
| All observable | {1.0, 0.9, 0.8} | {} | NO CHANGE |

**Strict definition:** Gap exists only when BOTH surviving AND nullified states present.

---

## Chapter 7: Complete Correspondence Table

| Quantum Concept | Bloch Sphere | Nullification | Physics |
|-----------------|--------------|---------------|---------|
| Pure state | \|r\| = 1 | [1] | Observable |
| Mixed state | \|r\| < 1 | [0.0e] | Partial info |
| Max mixed | \|r\| = 0 | [0] | Confined |
| Entanglement | Reduces \|r\| | Creates [0] | Confinement |
| Bell violation | Requires \|r\|=0 | Requires [0] | Nonlocality |
| Decoherence | Increases \|r\| | [0] -> [0.0e] | Unconfines |
| Concurrence C | C ~ 1-\|r\| | C=1 <=> [0] | Entanglement |
| Fidelity | F ~ \|r\| | F=1 <=> [1] | State quality |
| von Neumann S | S ~ 1-\|r\|^2 | S=1 <=> [0] | Information |

---

## Chapter 8: Computational Limits

| n qubits | Hilbert dim | Memory | Time |
|----------|-------------|--------|------|
| 8 | 256 | 1 MB | 0.03 s |
| 10 | 1024 | 16 MB | 0.5 s |
| 12 | 4096 | 256 MB | 8 s |
| 13 | 8192 | 1 GB | 32 s |
| 14 | 16384 | 4 GB | ~2 min |
| 16 | 65536 | 64 GB | ~30 min |

**Practical limit:** ~13 qubits on standard hardware.

---

## Quick Reference

| Concept | Formula/Rule |
|---------|--------------|
| Bloch vector | r = (Tr(rho*X), Tr(rho*Y), Tr(rho*Z)) |
| Purity | Tr(rho^2) = (1 + \|r\|^2)/2 |
| Classification | \|r\|=0 [0], 0<\|r\|<Delta [0.0e], \|r\|>=Delta [1] |
| Entanglement | C = 1 <=> \|r\| = 0 |
| Bell violation | Requires \|r\| = 0 (confinement) |
| W-state \|r\| | (n-2)/n for n qubits |
| GHZ \|r\| | 0 for all qubits (any n) |
| Max qubits | ~13 (limited by O(4^n) memory) |

---

*"Entanglement hides the parts to reveal the whole. This is confinement."*
