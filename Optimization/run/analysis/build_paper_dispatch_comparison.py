from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", action="append", required=True, help="Run directory containing dispatch_kpis.json")
    ap.add_argument("--label", action="append", default=None, help="Optional label matching each --run-dir in order")
    ap.add_argument("--output-dir", type=str, default=None, help="Optional output directory")
    return ap.parse_args()


def build_paper_dispatch_comparison(
    *,
    run_dirs: list[Path],
    labels: list[str] | None = None,
    output_dir: Path | None = None,
) -> Path:
    if not run_dirs:
        raise ValueError("[paper_compare] run_dirs is empty.")
    resolved_run_dirs = [Path(p).resolve() for p in run_dirs]
    resolved_output_dir = (
        Path(output_dir).resolve() if output_dir is not None else _default_output_dir(resolved_run_dirs).resolve()
    )
    rows = _build_rows(resolved_run_dirs, list(labels or []))
    df = _write_outputs(resolved_output_dir, rows)
    _save_plots(resolved_output_dir, df)
    return resolved_output_dir


def _load_latest_point(run_dir: Path) -> dict[str, Any]:
    dispatch_path = run_dir / "dispatch_kpis.json"
    if not dispatch_path.exists():
        raise FileNotFoundError(f"[paper_compare] dispatch_kpis.json not found: {dispatch_path}")
    payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"[paper_compare] {dispatch_path} is not a JSON object.")
    latest = payload.get("latest_point")
    if not isinstance(latest, dict) or not latest:
        raise ValueError(f"[paper_compare] latest_point missing in {dispatch_path}")
    return latest


def _default_output_dir(run_dirs: list[Path]) -> Path:
    parent = run_dirs[0].parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return parent / f"paper_dispatch_comparison_{ts}"


def _build_rows(run_dirs: list[Path], labels: list[str] | None) -> list[dict[str, Any]]:
    if labels and len(labels) != len(run_dirs):
        raise ValueError("[paper_compare] Number of --label values must match --run-dir.")
    rows: list[dict[str, Any]] = []
    for idx, run_dir in enumerate(run_dirs):
        latest = _load_latest_point(run_dir)
        label = labels[idx] if labels else run_dir.name
        row = {
            "case_label": label,
            "run_dir": str(run_dir),
            **latest,
        }
        rows.append(row)
    if not rows:
        raise ValueError("[paper_compare] No rows loaded.")
    baseline = rows[0]
    delta_keys = [
        "dispatch_objective_eur",
        "dispatch_operating_cost_eur",
        "dispatch_penalty_total_eur",
        "co2_emissions_total_t",
        "dh_unserved_heat_kwh",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
    ]
    for row in rows:
        for key in delta_keys:
            if key not in row:
                raise KeyError(f"[paper_compare] Required comparison key missing: {key}")
            row[f"delta_vs_{baseline['case_label']}_{key}"] = float(row[key]) - float(baseline[key])
    return rows


def _write_outputs(output_dir: Path, rows: list[dict[str, Any]]) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    csv_path = output_dir / "paper_dispatch_comparison.csv"
    json_path = output_dir / "paper_dispatch_comparison.json"
    md_path = output_dir / "paper_dispatch_comparison.md"
    df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_cols = [
        "case_label",
        "dispatch_objective_eur",
        "dispatch_operating_cost_eur",
        "dispatch_penalty_total_eur",
        "co2_emissions_total_t",
        "dh_unserved_heat_kwh",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_additional_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_peak_change_kw",
    ]
    with md_path.open("w", encoding="utf-8") as fh:
        fh.write("# Paper Dispatch Comparison\n\n")
        fh.write(df[summary_cols].to_string(index=False))
        fh.write("\n")
    return df


def _save_plots(output_dir: Path, df: pd.DataFrame) -> None:
    labels = df["case_label"].astype(str).tolist()
    x = range(len(labels))

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    ax = axes[0, 0]
    width = 0.25
    ax.bar([i - width for i in x], df["dispatch_operating_cost_eur"] / 1e6, width=width, label="Operating")
    ax.bar(list(x), df["dispatch_penalty_total_eur"] / 1e6, width=width, label="Penalties")
    ax.bar([i + width for i in x], df["dispatch_objective_eur"] / 1e6, width=width, label="Objective")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("EUR million / slice")
    ax.set_title("Dispatch Cost Split")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()

    ax = axes[0, 1]
    ax.bar(labels, df["co2_emissions_total_t"])
    ax.set_ylabel("t CO2 / slice")
    ax.set_title("Operational CO2")
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=15)

    ax = axes[1, 0]
    ax.bar(labels, df["dh_unserved_heat_kwh"] / 1e3)
    ax.set_ylabel("MWh / slice")
    ax.set_title("District Heat Unserved")
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=15)

    ax = axes[1, 1]
    width = 0.25
    ax.bar([i - width for i in x], df["thermflex_shifted_space_heat_kwh"] / 1e3, width=width, label="Shifted")
    ax.bar(list(x), df["thermflex_additional_space_heat_kwh"] / 1e3, width=width, label="Additional")
    ax.bar([i + width for i in x], df["thermflex_rebound_kwh"] / 1e3, width=width, label="Rebound")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("MWh / slice")
    ax.set_title("Thermflex Energy Effects")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_dir / "paper_dispatch_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = _parse_args()
    output_dir = build_paper_dispatch_comparison(
        run_dirs=[Path(p) for p in args.run_dir],
        labels=list(args.label or []),
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(f"[paper_compare] output_dir={output_dir}")


if __name__ == "__main__":
    main()
