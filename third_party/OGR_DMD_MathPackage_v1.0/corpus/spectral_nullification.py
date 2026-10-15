import numpy as np

# Spectral nullification instrument for the Messina Nullification Framework.
# Distinguishes the genuine spectral operator T_Δ (functional calculus)
# from projector sandwiching N·A·N, and reports whether a claimed gap is
# structural or imposed.

def nullify(lam, D):
    return lam if abs(lam) >= D else 0.0

def T_delta(A, D):
    # Honest spectral nullification: threshold A's own eigenvalues.
    w, V = np.linalg.eigh(A)
    wn = np.array([nullify(l, D) for l in w])
    return (V * wn) @ V.T, w, wn

def sandwich(A, N):
    # Projector form used in the QFT documents: N = ∏ Pⱼ.
    return N @ A @ N

def spectral_projector(A, D):
    # The ONLY N for which σ(NAN) = {0} ∪ [Δ,∞) exactly.
    w, V = np.linalg.eigh(A)
    keep = np.array([1.0 if abs(l) >= D else 0.0 for l in w])
    return (V * keep) @ V.T

def gap_is_empty(spectrum, D, tol=1e-9):
    return all((abs(l) < tol) or (abs(l) >= D) for l in spectrum)

def diagnose(A, D, N=None, name="operator"):
    A = np.asarray(A, float)
    An, w, wn = T_delta(A, D)
    print(f"── {name} (Δ={D}) ──")
    print(f"  eigenvalues(A)          : {np.round(w,4)}")
    print(f"  T_Δ nullified spectrum  : {np.round(wn,4)}")
    print(f"  T_Δ gap (0,Δ) empty     : {gap_is_empty(wn, D)}  (tautological)")
    print(f"  T_Δ symmetric/idempotent: "
          f"{np.allclose(An,An.T)} / {np.allclose(T_delta(An,D)[0],An)}")
    if N is not None:
        N = np.asarray(N, float)
        wN = np.linalg.eigvalsh(sandwich(A, N))
        aligned = np.allclose(N, spectral_projector(A, D))
        print(f"  σ(N·A·N)                : {np.round(wN,4)}")
        print(f"  N aligned w/ ≥Δ eigsp.  : {aligned}")
        print(f"  N·A·N gap (0,Δ) empty   : {gap_is_empty(wN, D)}"
              f"{'' if aligned else '  <-- NOT guaranteed; N misaligned'}")
    print()

if __name__ == "__main__":
    A = [[2.0, 0.7], [0.7, 0.5]]
    # Generic (misaligned) projector: manufactures an in-gap mode.
    u = np.array([np.cos(1.4), np.sin(1.4)]); Nbad = np.outer(u, u)
    # The correct spectral projector: reproduces the T_Δ gap.
    Ngood = spectral_projector(np.asarray(A, float), 1.0)
    diagnose(A, 1.0, Nbad,  "misaligned N·A·N")
    diagnose(A, 1.0, Ngood, "aligned N·A·N")
