#!/usr/bin/env python3
"""
Nullification Geometry - Mathematical Verification Script

Author: Joseph Messina
Date: December 2025
License: CC-BY 4.0

This script verifies all mathematical claims in the Nullification Geometry Workbook.
Run this to replicate the test results.

Requirements: numpy (pip install numpy)
"""

import numpy as np
from typing import Tuple, List, Dict

# =============================================================================
# CONFIGURATION
# =============================================================================

DELTA = 1.0  # Default threshold

# =============================================================================
# CORE NULLIFICATION FUNCTIONS
# =============================================================================

def N_scalar(x: float, delta: float = DELTA) -> float:
    """Scalar nullification operator."""
    return x if abs(x) >= delta else 0.0

def R_scalar(x: float, delta: float = DELTA) -> float:
    """Scalar remainder operator."""
    return x - N_scalar(x, delta)

def classify_scalar(x: float, delta: float = DELTA) -> str:
    """Classify a scalar value."""
    if x == 0:
        return "[0]"
    elif abs(x) >= delta:
        return "[1]"
    else:
        return "[0.0e]"

# =============================================================================
# VECTOR NULLIFICATION - TWO APPROACHES
# =============================================================================

def N_vector_componentwise(v: np.ndarray, delta: float = DELTA) -> np.ndarray:
    """Apply N to each component independently."""
    return np.array([N_scalar(x, delta) for x in v])

def R_vector_componentwise(v: np.ndarray, delta: float = DELTA) -> np.ndarray:
    """Remainder for componentwise approach."""
    return v - N_vector_componentwise(v, delta)

def N_vector_norm(v: np.ndarray, delta: float = DELTA) -> np.ndarray:
    """Apply N based on vector magnitude (norm)."""
    norm = np.linalg.norm(v)
    return v if norm >= delta else np.zeros_like(v)

def R_vector_norm(v: np.ndarray, delta: float = DELTA) -> np.ndarray:
    """Remainder for norm-based approach."""
    return v - N_vector_norm(v, delta)

# =============================================================================
# POINT CLASSIFICATION
# =============================================================================

def classify_point(p: np.ndarray, delta: float = DELTA) -> str:
    """Classify point based on distance from origin."""
    dist = np.linalg.norm(p)
    if dist == 0:
        return "[0]"
    elif dist >= delta:
        return "[1]"
    else:
        return "[0.0e]"

# =============================================================================
# TRIANGLE GEOMETRY
# =============================================================================

def triangle_area(a: float, b: float, c: float) -> float:
    """Calculate triangle area using Heron's formula."""
    s = (a + b + c) / 2
    val = s * (s - a) * (s - b) * (s - c)
    if val < 0:
        return 0.0  # Invalid triangle
    return np.sqrt(val)

def analyze_triangle(sides: Tuple[float, float, float], delta: float = DELTA) -> Dict:
    """Complete analysis of a triangle."""
    a, b, c = sides
    perimeter = a + b + c
    area = triangle_area(a, b, c)
    
    return {
        'sides': sides,
        'side_classes': [classify_scalar(x, delta) for x in sides],
        'perimeter': perimeter,
        'perimeter_class': classify_scalar(perimeter, delta),
        'area': area,
        'area_class': classify_scalar(area, delta)
    }

def scale_triangle(base: Tuple[float, float, float], k: float) -> Tuple[float, float, float]:
    """Scale a triangle by factor k."""
    return tuple(x * k for x in base)

# =============================================================================
# MATRIX EIGENVALUE NULLIFICATION
# =============================================================================

def N_eigenvalues(A: np.ndarray, delta: float = DELTA) -> Tuple[np.ndarray, np.ndarray]:
    """
    Nullify eigenvalues below threshold.
    Returns (nullified_eigenvalues, original_eigenvalues)
    """
    eigenvalues, _ = np.linalg.eig(A)
    eigenvalues = np.real(eigenvalues)  # For real symmetric matrices
    n_eigenvalues = np.array([N_scalar(ev, delta) for ev in eigenvalues])
    return n_eigenvalues, eigenvalues

def has_spectral_gap(nullified_eigs: np.ndarray, delta: float = DELTA) -> bool:
    """Check if nullification created a spectral gap."""
    has_zero = 0.0 in nullified_eigs or any(abs(e) < 1e-10 for e in nullified_eigs)
    has_nonzero = any(abs(e) >= delta for e in nullified_eigs)
    return has_zero and has_nonzero

# =============================================================================
# TEST SUITE
# =============================================================================

def test_section_1_vectors():
    """Test vector nullification - both approaches."""
    print("=" * 70)
    print("SECTION 1: VECTOR NULLIFICATION")
    print("=" * 70)
    
    test_vectors = [
        np.array([0.3, 0.4]),        # Both < 1, norm = 0.5
        np.array([0.6, 0.8]),        # Both < 1, norm = 1.0 (boundary!)
        np.array([0.3, 1.5]),        # Mixed: one < 1, one >= 1
        np.array([1.2, 1.5]),        # Both >= 1
        np.array([0.5, 0.5, 0.5]),   # 3D: all < 1, norm = 0.866
        np.array([0.6, 0.6, 0.6]),   # 3D: all < 1, norm = 1.039 >= 1
    ]
    
    print("\nComparing Component-wise vs Norm-based approaches:\n")
    print(f"{'Vector':<25} {'Norm':>8} {'N_comp':<20} {'N_norm':<20} {'Same?'}")
    print("-" * 85)
    
    results = []
    for v in test_vectors:
        norm = np.linalg.norm(v)
        n_comp = N_vector_componentwise(v)
        n_norm = N_vector_norm(v)
        same = np.allclose(n_comp, n_norm)
        results.append(same)
        print(f"{str(v):<25} {norm:>8.3f} {str(n_comp):<20} {str(n_norm):<20} {same}")
    
    # Conservation check
    print("\n--- Conservation Check (N + R = v) ---")
    all_conserved = True
    for v in test_vectors[:3]:
        n_c = N_vector_componentwise(v)
        r_c = R_vector_componentwise(v)
        conserved_c = np.allclose(n_c + r_c, v)
        
        n_n = N_vector_norm(v)
        r_n = R_vector_norm(v)
        conserved_n = np.allclose(n_n + r_n, v)
        
        all_conserved = all_conserved and conserved_c and conserved_n
        print(f"v = {v}: Componentwise: {conserved_c}, Norm: {conserved_n}")
    
    print(f"\n[OK] All conservation tests passed: {all_conserved}")
    return all_conserved


def test_section_2_points():
    """Test point classification by distance."""
    print("\n" + "=" * 70)
    print("SECTION 2: POINTS AND DISTANCE (2D/3D)")
    print("=" * 70)
    
    points_2d = [
        np.array([0.0, 0.0]),
        np.array([0.3, 0.4]),
        np.array([0.6, 0.8]),
        np.array([1.0, 0.0]),
        np.array([0.8, 0.8]),
        np.array([2.0, 2.0]),
    ]
    
    print("\n2D Point Classification:\n")
    print(f"{'Point':<20} {'Distance':>10} {'Class':<10}")
    print("-" * 45)
    for p in points_2d:
        dist = np.linalg.norm(p)
        cls = classify_point(p)
        print(f"{str(p):<20} {dist:>10.3f} {cls:<10}")
    
    points_3d = [
        np.array([0.5, 0.5, 0.5]),
        np.array([0.6, 0.6, 0.6]),
        np.array([1.0, 0.0, 0.0]),
    ]
    
    print("\n3D Point Classification:\n")
    for p in points_3d:
        dist = np.linalg.norm(p)
        cls = classify_point(p)
        print(f"Point {p}: distance = {dist:.3f}, class = {cls}")
    
    # Verify key examples
    p_boundary = np.array([0.6, 0.8])
    assert classify_point(p_boundary) == "[1]", "Boundary point should be [1]"
    
    p_3d_under = np.array([0.5, 0.5, 0.5])
    assert classify_point(p_3d_under) == "[0.0e]", "Point with norm < 1 should be [0.0e]"
    
    p_3d_over = np.array([0.6, 0.6, 0.6])
    assert classify_point(p_3d_over) == "[1]", "Point with norm >= 1 should be [1]"
    
    print("\n[OK] All point classification tests passed")
    return True


def test_section_3_triangles():
    """Test triangle geometry analysis."""
    print("\n" + "=" * 70)
    print("SECTION 3: TRIANGLE GEOMETRY")
    print("=" * 70)
    
    triangles = [
        (3, 4, 5),
        (0.3, 0.4, 0.5),
        (0.6, 0.8, 1.0),
        (1.5, 2.0, 2.5),
        (0.5, 1.2, 1.3),
    ]
    
    print("\nTriangle Analysis:\n")
    print(f"{'Sides':<20} {'Perimeter':>10} {'P class':<8} {'Area':>10} {'A class':<8}")
    print("-" * 65)
    
    for sides in triangles:
        r = analyze_triangle(sides)
        print(f"{str(sides):<20} {r['perimeter']:>10.3f} {r['perimeter_class']:<8} {r['area']:>10.3f} {r['area_class']:<8}")
    
    # Key finding: pool accumulation
    print("\n--- Key Finding: Pool Accumulation ---")
    t = (0.4, 0.4, 0.4)
    r = analyze_triangle(t)
    print(f"Triangle {t}:")
    print(f"  Side classes: {r['side_classes']}")
    print(f"  Perimeter = {r['perimeter']:.3f} -> {r['perimeter_class']} (OBSERVABLE!)")
    print(f"  Area = {r['area']:.3f} -> {r['area_class']}")
    
    # Verify: all [0.0e] sides, [1] perimeter
    assert all(c == "[0.0e]" for c in r['side_classes']), "All sides should be [0.0e]"
    assert r['perimeter_class'] == "[1]", "Perimeter should be [1]"
    
    print("\n[OK] Triangle pool accumulation verified")
    return True


def test_section_4_scaling():
    """Test scaling effects on triangles."""
    print("\n" + "=" * 70)
    print("SECTION 4: SCALING EFFECTS")
    print("=" * 70)
    
    base = (3, 4, 5)
    scales = [1.0, 0.5, 0.3, 0.2, 0.1]
    
    print(f"\nScaling triangle {base}:\n")
    print(f"{'Scale':<8} {'Sides':<25} {'Side Classes':<20} {'Perim':<8} {'P_cls':<8} {'Area':<8} {'A_cls'}")
    print("-" * 95)
    
    for k in scales:
        scaled = scale_triangle(base, k)
        r = analyze_triangle(scaled)
        sides_str = f"({scaled[0]:.2f}, {scaled[1]:.2f}, {scaled[2]:.2f})"
        cls_str = ', '.join(r['side_classes'])
        print(f"{k:<8} {sides_str:<25} {cls_str:<20} {r['perimeter']:<8.2f} {r['perimeter_class']:<8} {r['area']:<8.2f} {r['area_class']}")
    
    # Verify area scales as k^2
    k = 0.5
    original_area = triangle_area(*base)
    scaled_area = triangle_area(*scale_triangle(base, k))
    expected = original_area * k**2
    assert abs(scaled_area - expected) < 1e-10, "Area should scale as k^2"
    
    print("\n[OK] Scaling verified (area ~ kÂ²)")
    return True


def test_section_5_matrices():
    """Test matrix eigenvalue nullification."""
    print("\n" + "=" * 70)
    print("SECTION 5: MATRIX EIGENVALUE NULLIFICATION")
    print("=" * 70)
    
    matrices = [
        ("Diagonal: one above, one below", np.array([[2.0, 0.0], [0.0, 0.5]])),
        ("Both below threshold", np.array([[0.3, 0.0], [0.0, 0.4]])),
        ("Both above threshold", np.array([[1.5, 0.0], [0.0, 2.0]])),
        ("Boundary + below", np.array([[1.0, 0.0], [0.0, 0.5]])),
        ("Off-diagonal", np.array([[0.6, 0.8], [0.8, 0.6]])),
    ]
    
    print("\nMatrix Eigenvalue Nullification:\n")
    
    for name, A in matrices:
        n_eigs, orig_eigs = N_eigenvalues(A)
        orig_classes = [classify_scalar(ev) for ev in orig_eigs]
        gap = has_spectral_gap(n_eigs)
        
        print(f"{name}:")
        print(f"  Original eigenvalues: {orig_eigs}")
        print(f"  Classifications: {orig_classes}")
        print(f"  Nullified eigenvalues: {n_eigs}")
        print(f"  Spectral gap created: {gap}")
        print()
    
    # Verify specific case
    A = np.array([[2.0, 0.0], [0.0, 0.5]])
    n_eigs, _ = N_eigenvalues(A)
    assert np.allclose(n_eigs, [2.0, 0.0]), "Should nullify 0.5 to 0"
    
    print("[OK] Matrix eigenvalue nullification verified")
    return True


def test_section_6_nondistributivity():
    """Test non-distributivity in vectors."""
    print("\n" + "=" * 70)
    print("SECTION 6: NON-DISTRIBUTIVITY IN VECTORS")
    print("=" * 70)
    
    # Good example showing non-distributivity
    u = np.array([0.6, 0.6])
    v = np.array([0.6, 0.6])
    
    print(f"\nTesting with u = {u}, v = {v}")
    print(f"||u|| = {np.linalg.norm(u):.3f}")
    print(f"||v|| = {np.linalg.norm(v):.3f}")
    print(f"||u+v|| = {np.linalg.norm(u+v):.3f}")
    
    n_u = N_vector_norm(u)
    n_v = N_vector_norm(v)
    n_sum = N_vector_norm(u + v)
    
    print(f"\nNorm-based approach:")
    print(f"  N(u) = {n_u}")
    print(f"  N(v) = {n_v}")
    print(f"  N(u) + N(v) = {n_u + n_v}")
    print(f"  N(u + v) = {n_sum}")
    
    is_equal = np.allclose(n_u + n_v, n_sum)
    print(f"  Equal? {is_equal}")
    
    # Verify non-distributivity
    assert not is_equal, "Should demonstrate non-distributivity"
    print("\n[OK] Non-distributivity confirmed!")
    
    # Verify conservation still holds
    r_sum = (u + v) - N_vector_norm(u + v)
    conserved = np.allclose(N_vector_norm(u + v) + r_sum, u + v)
    print(f"\nConservation: N(u+v) + R(u+v) = {N_vector_norm(u+v) + r_sum}")
    print(f"u + v = {u + v}")
    print(f"Match? {conserved}")
    
    assert conserved, "Conservation must hold"
    print("\n[OK] Conservation verified despite non-distributivity")
    return True


def run_all_tests():
    """Run complete test suite."""
    print("\n" + "=" * 70)
    print("NULLIFICATION GEOMETRY - MATHEMATICAL VERIFICATION")
    print("=" * 70)
    print(f"Threshold Î” = {DELTA}")
    print("=" * 70)
    
    results = []
    
    results.append(("Vectors", test_section_1_vectors()))
    results.append(("Points", test_section_2_points()))
    results.append(("Triangles", test_section_3_triangles()))
    results.append(("Scaling", test_section_4_scaling()))
    results.append(("Matrices", test_section_5_matrices()))
    results.append(("Non-Distributivity", test_section_6_nondistributivity()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {name}: {status}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED - MATHEMATICS VERIFIED")
    else:
        print("SOME TESTS FAILED - CHECK OUTPUT")
    print("=" * 70)
    
    return all_passed


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
