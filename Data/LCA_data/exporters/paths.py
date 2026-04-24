from __future__ import annotations

import sys
from pathlib import Path


def find_repo_root() -> Path:
    """Find repo root by walking up until a 'Data' directory exists."""
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    # fallback: adjust if your layout differs
    return here.parents[3]


def lca_data_dir() -> Path:
    return find_repo_root() / "Data" / "LCA_data"


def ensure_lca_data_on_syspath() -> Path:
    """
    Ensure Data/LCA_data is importable so exporters can import calculators/ etc.
    Returns the LCA_data dir.
    """
    base = lca_data_dir()
    s = str(base)
    if s not in sys.path:
        sys.path.insert(0, s)
    return base
