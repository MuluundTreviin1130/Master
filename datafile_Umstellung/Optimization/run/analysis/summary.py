from __future__ import annotations
import os
import numpy as np

def _range_str(a: np.ndarray) -> str:
    return f"[{np.min(a):.3g} … {np.max(a):.3g}]"

def write_summary(run_dir: str, settings, X_opt: np.ndarray, F_opt: np.ndarray) -> None:
    X = np.asarray(X_opt, float) if X_opt is not None else None
    F = np.asarray(F_opt, float) if F_opt is not None else None

    lines: list[str] = []
    lines.append("=== Optimization Summary ===")
    lines.append(f"Engine: {settings.engine.name}")
    lines.append(f"System: {settings.engine.system_id} @ {settings.engine.location}")
    lines.append(f"EC shares (import/export): {settings.engine.ec_share_import}/{settings.engine.ec_share_export}")
    lines.append(
        f"N_HH={settings.engine.N_HH}, "
        f"N_EV_total={settings.engine.N_EV_total}, "
        f"N_EV_bidirectional={settings.engine.N_EV_bidirectional}"
    )
    lines.append("")
    lines.append(f"Design vars: {settings.bounds.names}")
    lines.append(f"Bounds: lower={settings.bounds.lower}, upper={settings.bounds.upper}")
    lines.append(f"Objectives: {settings.objectives.names} (minimize={settings.objectives.minimize})")
    if settings.constraints.names:
        lines.append(f"Constraints (<=0): {list(zip(settings.constraints.names, settings.constraints.senses, settings.constraints.rhs))}")
    lines.append("")
    lines.append(f"Sampler: {settings.sampler.name} (n={settings.sampler.n_samples}, seed={settings.sampler.seed})")
    lines.append(f"Optimizer: {settings.optimizer.name} {settings.optimizer.kwargs} (seed={settings.optimizer.seed})")
    lines.append("")

    if X is not None and X.size:
        lines.append("X ranges: " + ", ".join(f"{n}={_range_str(X[:, i])}" for i, n in enumerate(settings.bounds.names)))
    if F is not None and F.size:
        lines.append("F ranges: " + ", ".join(f"{n}={_range_str(F[:, i])}" for i, n in enumerate(settings.objectives.names)))

    out_txt = os.path.join(run_dir, "summary.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
