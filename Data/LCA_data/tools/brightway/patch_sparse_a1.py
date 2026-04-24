from __future__ import annotations

"""Compatibility patch for SciPy sparse matrices.

Some `matrix_utils` versions used by Brightway expect sparse matrices to provide
`.A1` (flattened dense array), but SciPy sparse matrices historically expose
`.A` only.

On newer SciPy versions `.A1` might exist, on older ones it doesn't. This patch
adds a read-only `A1` property to common sparse matrix classes.
"""


def patch_sparse_A1() -> None:
    try:
        import scipy.sparse as sp
    except Exception:
        return

    def _a1(self):  # type: ignore[no-redef]
        # `.A` yields a dense ndarray; flatten to 1D
        return self.A.ravel()

    for cls in (sp.csc_matrix, sp.csr_matrix, sp.coo_matrix, sp.lil_matrix, sp.dok_matrix):
        if not hasattr(cls, "A1"):
            try:
                cls.A1 = property(_a1)  # type: ignore[attr-defined]
            except Exception:
                pass
