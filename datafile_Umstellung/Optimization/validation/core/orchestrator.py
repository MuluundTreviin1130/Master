# Optimization/validation/core/orchestrator.py
from __future__ import annotations

from typing import Dict, Any
from pathlib import Path
import pandas as pd

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.core.settings_access import get_settings_with_validation
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.core.input_builder import build_X_from_bounds
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.core.reporting import (
    write_audit_and_probes,
    write_predictions,
    write_metrics_and_report,
)
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.engines.runner import run_fast, run_gold
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.io.writers import ensure_out_dir


def validate(cfg: Dict[str, Any]) -> None:
    """
    Schlanker Orchestrator:
    - holt Settings (Single Source of Truth)
    - nimmt X & Meta aus cfg (oder baut X aus Bounds)
    - ruft Teachers (FAST/GOLD)
    - schreibt Audit, Probes, Predictions, Metrics, Plots, MD-Report
    """
    S = get_settings_with_validation()
    V = getattr(S, "validation", None)
    run_cfg = getattr(S, "run", None)

    run_id = getattr(V, "run_id", None) or getattr(run_cfg, "tag", None) or "validation_run"

    # Output-Basis: bevorzugt Validation-Reporting, sonst Optimierungs-Reporting
    out_base = None
    if V is not None and getattr(V, "reporting", None) is not None:
        out_base = getattr(V.reporting, "output_root", None)
    if out_base is None:
        out_base = getattr(getattr(S, "reporting", None), "output_root", "Optimization/validation/results")

    out_root = ensure_out_dir(out_base, run_id, timestamping=True)

    # X & Meta holen / bauen
    X: pd.DataFrame | None = cfg.get("X")
    meta: Dict[str, Any] = cfg.get("meta", {}) or {}
    if X is None:
        X = build_X_from_bounds(S)

    xnames = list(getattr(getattr(S, "bounds", None), "names", X.columns.to_list()))
    X = X.loc[:, xnames]

    audit = write_audit_and_probes(out_root, S, run_id, X)

    bounds_dict = {
        name: (float(lo), float(up))
        for name, lo, up in zip(
            getattr(S.bounds, "names", []),
            getattr(S.bounds, "lower", []),
            getattr(S.bounds, "upper", []),
        )
    }

    teacher_mode = getattr(V, "teacher_mode", "fast+gold") if V is not None else "fast+gold"

    F_fast = K_fast = F_gold = K_gold = None

    if "fast" in teacher_mode:
        F_fast, K_fast = run_fast(X, xnames, bounds_dict, meta, S.engine)

    if "gold" in teacher_mode:
        F_gold, K_gold = run_gold(X, xnames, bounds_dict, meta, S.engine)

    write_predictions(out_root, X, F_fast, K_fast, F_gold, K_gold)
    write_metrics_and_report(out_root, run_id, S, F_fast, F_gold)

    print(f"[validation] finished. Outputs under: {Path(out_root).resolve()}")
