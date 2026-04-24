from __future__ import annotations

from pathlib import Path

def find_project_root(start: Path | None = None) -> Path:
    """Walk upwards until we find a folder containing 'Data/'.

    This mirrors the logic used in Data/LCA_data/lca_facade.py
    so tools can be run from arbitrary working directories.
    """
    here = (start or Path(__file__)).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    # fallback: two levels above tools/
    return here.parents[5]
