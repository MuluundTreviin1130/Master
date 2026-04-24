from __future__ import annotations

from pathlib import Path


def project_root(marker_dir: str = "Data") -> Path:
    """Find project root by walking upwards until a `marker_dir/` folder exists."""
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / marker_dir).exists():
            return p
    # Fallback: three levels up is usually the repo root in this project.
    return here.parents[3]


def lca_data_dir() -> Path:
    """Return `<project_root>/Data/LCA_data`."""
    return project_root() / "Data" / "LCA_data"
