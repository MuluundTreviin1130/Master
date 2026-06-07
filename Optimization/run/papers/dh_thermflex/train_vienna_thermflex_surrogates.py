from __future__ import annotations

import json
from pathlib import Path
import sys

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError("[train_vienna_thermflex_surrogates] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Settings import get_settings
from Optimization.framework.engines.Surrogat_model.training import auto_train_surrogate
from Optimization.framework.engines.Gated.io import promote_surrogate_version
from Optimization.run.runners.train_surrogate import _build_signature_hash


DEFAULT_CASES = (
    Path("Optimization")
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex",
    (
        "vienna_ref2023_dh_baseline_constant_no_thermflex_surrogate_train.json",
        "vienna_ref2023_dh_day_night_no_thermflex_surrogate_train.json",
        "vienna_ref2023_dh_day_night_thermflex_surrogate_train.json",
    ),
)


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"[train_vienna_thermflex_surrogates] overrides file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    base_dir, filenames = DEFAULT_CASES
    for filename in filenames:
        path = base_dir / filename
        overrides = _load_overrides(path)
        settings = get_settings(overrides=overrides)
        artifact_path = auto_train_surrogate(settings)
        out_dir = Path(artifact_path).resolve().parent
        sig_hash = _build_signature_hash(settings)
        promote_surrogate_version(sig_hash, out_dir, run_dir=str(out_dir))
        print(
            f"[train_vienna_thermflex_surrogates] finished {filename} -> "
            f"Optimization/run/artifacts/surrogates/{sig_hash}/",
            flush=True,
        )
