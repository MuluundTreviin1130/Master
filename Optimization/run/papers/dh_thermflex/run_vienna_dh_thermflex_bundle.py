from __future__ import annotations

from pathlib import Path
import sys


current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError("[run_vienna_dh_thermflex_bundle] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Optimization.run.analysis.build_dh_thermflex_run_bundle import (  # noqa: E402
    build_dh_thermflex_run_bundle,
)


if __name__ == "__main__":
    output_dir = build_dh_thermflex_run_bundle()
    print(f"[run_vienna_dh_thermflex_bundle] output_dir={output_dir}")
