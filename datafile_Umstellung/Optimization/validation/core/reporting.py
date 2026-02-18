# Optimization/validation/core/reporting.py
from __future__ import annotations

from pathlib import Path
import pandas as pd

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.io.writers import (
    save_audit,
    save_probes,
    save_predictions,
    save_metrics,
    save_report_md,
)
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.io.plots import plot_scatter
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.metrics.pairwise_objectives import compute_pairwise_metrics


def write_audit_and_probes(out_root: Path, S, run_id: str, X: pd.DataFrame) -> dict:
    audit = {
        "run_id": run_id,
        "n_rows": int(len(X)),
        "xnames": list(getattr(getattr(S, "bounds", None), "names", X.columns.to_list())),
        "system_id": getattr(getattr(S, "engine", None), "system_id", ""),
        "teacher_mode": getattr(getattr(S, "validation", None), "teacher_mode", "fast+gold"),
    }
    save_audit(out_root, audit)
    save_probes(out_root, {"designs": X})
    return audit


def write_predictions(
    out_root: Path,
    X: pd.DataFrame,
    F_fast: pd.DataFrame | None,
    K_fast: pd.DataFrame | None,
    F_gold: pd.DataFrame | None,
    K_gold: pd.DataFrame | None,
) -> None:
    parts = []

    def stack(label: str, F: pd.DataFrame | None, K: pd.DataFrame | None):
        if F is None:
            return
        idx = F.index
        df = pd.concat(
            [
                X.loc[idx].reset_index(drop=True),
                F.reset_index(drop=True),
                (K.reset_index(drop=True) if K is not None and not K.empty else pd.DataFrame()),
            ],
            axis=1,
        )
        df.insert(0, "teacher", label)
        parts.append(df)

    stack("fast", F_fast, K_fast)
    stack("gold", F_gold, K_gold)

    if parts:
        tidy = pd.concat(parts, ignore_index=True)
        save_predictions(out_root, tidy)


def write_metrics_and_report(
    out_root: Path,
    run_id: str,
    S,
    F_fast: pd.DataFrame | None,
    F_gold: pd.DataFrame | None,
) -> None:
    obj_names = list(getattr(getattr(S, "objectives", None), "names", []))
    if not (F_fast is not None and F_gold is not None and obj_names):
        return

    metrics_flat = compute_pairwise_metrics(F_fast, F_gold, obj_names)
    save_metrics(out_root, "objectives_fast_vs_gold", metrics_flat)

    # Scatter Plot (GOLD als Referenz, FAST als Prädiktor)
    try:
        plot_scatter(out_root, F_gold[obj_names], F_fast[obj_names], "FAST_vs_GOLD")
    except Exception as exc:
        print(f"[validation][plots] scatter FAST_vs_GOLD failed: {exc}")

    # kurzer Markdown-Report
    lines = [
        "# Validation FAST vs GOLD",
        "",
        f"- run_id: `{run_id}`",
        f"- system_id: `{getattr(getattr(S, 'engine', None), 'system_id', '')}`",
        "",
        "## Metrics (FAST vs GOLD)",
    ]
    for name in obj_names:
        r2_key = f"{name}_r2"
        rmse_key = f"{name}_rmse"
        mape_key = f"{name}_mape"
        if r2_key in metrics_flat:
            lines.append(
                f"- **{name}**: R²={metrics_flat[r2_key]:.4f}, "
                f"RMSE={metrics_flat[rmse_key]:.4g}, "
                f"MAPE={metrics_flat[mape_key]:.2f}%"
            )
    save_report_md(out_root, "\n".join(lines))
