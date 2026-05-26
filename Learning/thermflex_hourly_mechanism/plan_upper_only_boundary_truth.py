from __future__ import annotations

"""Plan upper-only boundary truth around observed rebound failures.

The existing upper-only dur24 screen is exhausted. This planner therefore does
not look for more of the same days. It uses the current diagnostic outputs to
find zero/low-rebound days that the surrogate falsely activates, pairs them
with nearby high-rebound days, and emits a compact run plan for new sensitivity
truth around those boundary dates.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = (
    REPO_ROOT
    / "Learning"
    / "datasets"
    / "b3ffb29c985557eaeffb7f45837d7773b7544d56966802b76bd77a708901a768"
)
DEFAULT_MODEL_DIR = (
    REPO_ROOT
    / "Learning"
    / "models"
    / "thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_b3ffb29c9855_features_no_case_label_transforms_mechanism_mass_identity"
)
DEFAULT_OUTPUT_DIR = DEFAULT_MODEL_DIR / "diagnostics" / "upper_only_boundary_truth_plan"


def plan_upper_only_boundary_truth(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    daily_diagnostic_subdir: str = "upper_only_subcontracts_enhanced",
    trigger_contract_subdir: str = "upper_only_trigger_contract",
    trigger_classifier: str = "logistic_balanced",
    trigger_magnitude: str = "active_regressor",
    low_rebound_threshold_kwh: float = 250_000.0,
    high_rebound_threshold_kwh: float = 1_500_000.0,
    tau_values: tuple[int, ...] = (2, 4, 8, 12),
    duration_values: tuple[int, ...] = (1, 4, 8, 24),
) -> dict[str, Any]:
    """Create paired boundary anchors and recommended new truth variants."""

    dataset_root = Path(dataset_dir).resolve()
    model_root = Path(model_dir).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    daily = _load_daily_diagnostic_frame(
        model_dir=model_root,
        dataset_dir=dataset_root,
        daily_diagnostic_subdir=str(daily_diagnostic_subdir),
        trigger_contract_subdir=str(trigger_contract_subdir),
        trigger_classifier=str(trigger_classifier),
        trigger_magnitude=str(trigger_magnitude),
        low_rebound_threshold_kwh=float(low_rebound_threshold_kwh),
    )
    pairs = _build_boundary_pairs(
        daily=daily,
        low_rebound_threshold_kwh=float(low_rebound_threshold_kwh),
        high_rebound_threshold_kwh=float(high_rebound_threshold_kwh),
    )
    run_plan = _build_run_plan(
        pairs=pairs,
        tau_values=tuple(int(value) for value in tau_values),
        duration_values=tuple(int(value) for value in duration_values),
    )
    core_plan = run_plan.loc[run_plan["batch_tier"] <= 1].copy()

    pairs_csv = output_root / "upper_only_boundary_pairs.csv"
    run_plan_csv = output_root / "upper_only_boundary_truth_run_plan.csv"
    core_plan_csv = output_root / "upper_only_boundary_truth_run_plan_core.csv"
    summary_json = output_root / "upper_only_boundary_truth_summary.json"
    readme_path = output_root / "README.md"
    pairs.to_csv(pairs_csv, index=False)
    run_plan.to_csv(run_plan_csv, index=False)
    core_plan.to_csv(core_plan_csv, index=False)

    summary = {
        "dataset_dir": str(dataset_root),
        "model_dir": str(model_root),
        "daily_diagnostic_subdir": str(daily_diagnostic_subdir),
        "trigger_contract_subdir": str(trigger_contract_subdir),
        "trigger_classifier": str(trigger_classifier),
        "trigger_magnitude": str(trigger_magnitude),
        "low_rebound_threshold_kwh": float(low_rebound_threshold_kwh),
        "high_rebound_threshold_kwh": float(high_rebound_threshold_kwh),
        "boundary_pairs": int(len(pairs)),
        "false_active_anchor_days": int(pairs["low_day"].nunique()) if len(pairs) else 0,
        "high_rebound_pair_days": int(pairs["high_day"].nunique()) if len(pairs) else 0,
        "recommended_run_rows": int(len(run_plan)),
        "recommended_core_run_rows": int(len(core_plan)),
        "run_rows_by_tier": run_plan["batch_tier"].value_counts().sort_index().to_dict(),
        "tau_values": list(tau_values),
        "duration_values": list(duration_values),
        "outputs": {
            "pairs_csv": str(pairs_csv),
            "run_plan_csv": str(run_plan_csv),
            "core_plan_csv": str(core_plan_csv),
            "summary_json": str(summary_json),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    readme_path.write_text(_readme_text(summary), encoding="utf-8")
    return summary


def _load_daily_diagnostic_frame(
    *,
    model_dir: Path,
    dataset_dir: Path,
    daily_diagnostic_subdir: str,
    trigger_contract_subdir: str,
    trigger_classifier: str,
    trigger_magnitude: str,
    low_rebound_threshold_kwh: float,
) -> pd.DataFrame:
    """Merge diagnostic rows with the best persisted trigger predictions."""

    daily_csv = model_dir / "diagnostics" / str(daily_diagnostic_subdir) / "daily_rebound_gate_rows.csv"
    trigger_csv = model_dir / "diagnostics" / str(trigger_contract_subdir) / "trigger_contract_predictions.csv"
    truth_csv = dataset_dir / "truth_dataset.csv"
    for path in (daily_csv, trigger_csv, truth_csv):
        if not path.exists():
            raise FileNotFoundError(f"[upper_only_boundary_truth] missing required artifact: {path}")

    daily = pd.read_csv(daily_csv)
    trigger = pd.read_csv(trigger_csv)
    trigger = trigger.loc[
        (trigger["classifier"].astype(str) == str(trigger_classifier))
        & (trigger["magnitude"].astype(str) == str(trigger_magnitude))
    ].copy()
    if trigger.empty:
        raise ValueError(
            "[upper_only_boundary_truth] selected trigger prediction rows are missing: "
            f"classifier={trigger_classifier}, magnitude={trigger_magnitude}"
        )

    truth_meta = _load_daily_truth_meta(truth_csv)
    merged = daily.merge(
        trigger[
            [
                "run_dir",
                "day",
                "rebound_pred_kwh",
                "active_probability",
                "active_pred",
                "truth_active_250k",
            ]
        ],
        on=["run_dir", "day"],
        how="inner",
        validate="one_to_one",
    ).merge(
        truth_meta,
        on=["run_dir", "day"],
        how="left",
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("[upper_only_boundary_truth] merged diagnostic frame is empty.")
    merged["day"] = pd.to_datetime(merged["day"], errors="raise").dt.date.astype(str)
    merged["is_false_active_low_rebound"] = (
        (pd.to_numeric(merged["rebound_true_kwh"], errors="raise") <= float(low_rebound_threshold_kwh))
        & (pd.to_numeric(merged["rebound_pred_kwh"], errors="raise") > float(low_rebound_threshold_kwh))
    )
    return merged


def _load_daily_truth_meta(truth_csv: Path) -> pd.DataFrame:
    """Read one row per run/day with policy state needed for run planning."""

    columns = [
        "run_dir",
        "timestamp",
        "policy_tau_h",
        "thermflex_max_flex_duration_h",
        "thermflex_constant_lower_bound_c",
        "thermflex_day_lower_bound_c",
        "thermflex_night_lower_bound_c",
        "control_mode",
        "reference_control_mode",
        "flex_case_label",
    ]
    available = pd.read_csv(truth_csv, nrows=1).columns
    usecols = [column for column in columns if column in available]
    truth = pd.read_csv(truth_csv, usecols=usecols)
    truth["day"] = pd.to_datetime(truth["timestamp"], errors="raise").dt.date.astype(str)
    keep_columns = [column for column in usecols if column != "timestamp"] + ["day"]
    return truth[keep_columns].drop_duplicates(["run_dir", "day"], keep="first")


def _build_boundary_pairs(
    *,
    daily: pd.DataFrame,
    low_rebound_threshold_kwh: float,
    high_rebound_threshold_kwh: float,
) -> pd.DataFrame:
    """Pair false-active low-rebound days with nearby high-rebound cases."""

    low = daily.loc[daily["is_false_active_low_rebound"]].copy()
    high = daily.loc[pd.to_numeric(daily["rebound_true_kwh"], errors="raise") >= float(high_rebound_threshold_kwh)].copy()
    if low.empty:
        raise ValueError("[upper_only_boundary_truth] no false-active low-rebound anchors found.")
    if high.empty:
        raise ValueError("[upper_only_boundary_truth] no high-rebound pair candidates found.")

    rows: list[dict[str, Any]] = []
    for _, low_row in low.sort_values(["is_test", "day"], ascending=[False, True]).iterrows():
        candidates = high.loc[high["season_regime"].astype(str) == str(low_row["season_regime"])].copy()
        if candidates.empty:
            candidates = high.copy()
        candidates["boundary_distance"] = _boundary_distance(candidates, low_row)
        nearest = candidates.sort_values(["boundary_distance", "day"]).head(3)
        for rank, (_, high_row) in enumerate(nearest.iterrows(), start=1):
            rows.append(_pair_row(low_row=low_row, high_row=high_row, pair_rank=rank))
    return pd.DataFrame(rows).sort_values(["low_day", "pair_rank"]).reset_index(drop=True)


def _boundary_distance(candidates: pd.DataFrame, anchor: pd.Series) -> pd.Series:
    """Compute a transparent weather/load distance for pair selection."""

    temp_scale = 4.0
    load_scale = 6_000_000.0
    shifted_scale = 2_000_000.0
    return (
        (pd.to_numeric(candidates["t_outdoor_mean_c"], errors="raise") - float(anchor["t_outdoor_mean_c"])).abs()
        / temp_scale
        + (
            pd.to_numeric(candidates["q_ref_sum_kwh"], errors="raise")
            - float(anchor["q_ref_sum_kwh"])
        ).abs()
        / load_scale
        + (
            pd.to_numeric(candidates["shifted_true_kwh"], errors="raise")
            - float(anchor["shifted_true_kwh"])
        ).abs()
        / shifted_scale
    )


def _pair_row(*, low_row: pd.Series, high_row: pd.Series, pair_rank: int) -> dict[str, Any]:
    """Create one low/high boundary-pair row."""

    common = {
        "pair_rank": int(pair_rank),
        "season_regime": str(low_row["season_regime"]),
        "boundary_distance": float(high_row["boundary_distance"]),
        "low_day": str(low_row["day"]),
        "high_day": str(high_row["day"]),
        "low_is_test": bool(low_row["is_test"]),
        "high_is_test": bool(high_row["is_test"]),
        "low_run_dir": str(low_row["run_dir"]),
        "high_run_dir": str(high_row["run_dir"]),
        "low_rebound_true_kwh": float(low_row["rebound_true_kwh"]),
        "low_rebound_pred_kwh": float(low_row["rebound_pred_kwh"]),
        "high_rebound_true_kwh": float(high_row["rebound_true_kwh"]),
        "high_rebound_pred_kwh": float(high_row["rebound_pred_kwh"]),
        "low_t_outdoor_mean_c": float(low_row["t_outdoor_mean_c"]),
        "high_t_outdoor_mean_c": float(high_row["t_outdoor_mean_c"]),
        "low_q_ref_sum_kwh": float(low_row["q_ref_sum_kwh"]),
        "high_q_ref_sum_kwh": float(high_row["q_ref_sum_kwh"]),
        "low_shifted_true_kwh": float(low_row["shifted_true_kwh"]),
        "high_shifted_true_kwh": float(high_row["shifted_true_kwh"]),
        "low_raw_first_negative_hour": float(low_row["raw_first_negative_hour"]),
        "high_raw_first_negative_hour": float(high_row["raw_first_negative_hour"]),
        "low_mass_corrected_first_negative_hour": float(low_row["mass_corrected_first_negative_hour"]),
        "high_mass_corrected_first_negative_hour": float(high_row["mass_corrected_first_negative_hour"]),
    }
    for column in [
        "policy_tau_h",
        "thermflex_max_flex_duration_h",
        "thermflex_constant_lower_bound_c",
        "thermflex_day_lower_bound_c",
        "thermflex_night_lower_bound_c",
        "control_mode",
        "reference_control_mode",
        "flex_case_label",
    ]:
        if column in low_row.index:
            common[f"low_{column}"] = low_row[column]
        if column in high_row.index:
            common[f"high_{column}"] = high_row[column]
    return common


def _build_run_plan(
    *,
    pairs: pd.DataFrame,
    tau_values: tuple[int, ...],
    duration_values: tuple[int, ...],
) -> pd.DataFrame:
    """Expand boundary pairs into concrete tau/duration truth recommendations."""

    rows: list[dict[str, Any]] = []
    anchor_columns = [
        "low_day",
        "high_day",
        "season_regime",
        "boundary_distance",
        "low_rebound_true_kwh",
        "high_rebound_true_kwh",
        "low_t_outdoor_mean_c",
        "high_t_outdoor_mean_c",
        "low_q_ref_sum_kwh",
        "high_q_ref_sum_kwh",
    ]
    anchors = pairs.sort_values(["low_day", "pair_rank"]).drop_duplicates("low_day", keep="first")
    for _, pair in anchors.iterrows():
        for side in ("low", "high"):
            source_day = str(pair[f"{side}_day"])
            for tau in tau_values:
                for duration in duration_values:
                    priority = _run_priority(side=side, tau=int(tau), duration=int(duration))
                    row = {column: pair[column] for column in anchor_columns}
                    row.update(
                        {
                            "priority": int(priority),
                            "batch_tier": int(_batch_tier(side=side, tau=int(tau), duration=int(duration))),
                            "boundary_side": side,
                            "source_day": source_day,
                            "recommended_tau_h": int(tau),
                            "recommended_duration_h": int(duration),
                            "recommended_control_family": "upper_only",
                            "recommended_reason": (
                                "paired zero/high rebound boundary truth for Upper-only trigger separation"
                            ),
                        }
                    )
                    rows.append(row)
    plan = pd.DataFrame(rows)
    return plan.sort_values(
        ["batch_tier", "priority", "source_day", "boundary_side", "recommended_tau_h", "recommended_duration_h"]
    ).reset_index(drop=True)


def _run_priority(*, side: str, tau: int, duration: int) -> int:
    """Keep tau4/dur24 anchors first, then sensitivity variants."""

    side_offset = 0 if side == "low" else 1
    tau_rank = {4: 0, 8: 1, 2: 2, 12: 3}.get(int(tau), 9)
    duration_rank = {24: 0, 8: 1, 4: 2, 1: 3}.get(int(duration), 9)
    return side_offset * 1_000 + tau_rank * 100 + duration_rank


def _batch_tier(*, side: str, tau: int, duration: int) -> int:
    """Smallest useful batch first; full grid remains available."""

    if int(tau) == 4 and int(duration) == 24:
        return 0
    if int(tau) == 4 and int(duration) in {8, 4, 1}:
        return 1
    if int(duration) == 24 and int(tau) in {2, 8, 12}:
        return 2
    if str(side) == "low" and int(tau) in {8, 12} and int(duration) in {8, 4}:
        return 3
    return 4


def _readme_text(summary: dict[str, Any]) -> str:
    """Describe the boundary planning artifact."""

    return (
        "# Upper-only Boundary Truth Plan\n\n"
        "This diagnostic folder ranks paired zero/high rebound boundary days from "
        "existing learning truth and expands them into recommended tau/duration "
        "truth variants. It is intentionally not another model output.\n\n"
        "Files:\n"
        "- `upper_only_boundary_pairs.csv`: nearest high-rebound pairs for false-active low-rebound anchors.\n"
        "- `upper_only_boundary_truth_run_plan.csv`: concrete tau/duration rows for new truth collection.\n"
        "- `upper_only_boundary_truth_run_plan_core.csv`: tier-0/1 rows for the next compact batch.\n"
        "- `upper_only_boundary_truth_summary.json`: counts and source paths.\n\n"
        f"Boundary pairs: {summary['boundary_pairs']}; recommended run rows: "
        f"{summary['recommended_run_rows']}; core run rows: "
        f"{summary['recommended_core_run_rows']}.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--daily-diagnostic-subdir", default="upper_only_subcontracts_enhanced")
    parser.add_argument("--trigger-contract-subdir", default="upper_only_trigger_contract")
    parser.add_argument("--trigger-classifier", default="logistic_balanced")
    parser.add_argument("--trigger-magnitude", default="active_regressor")
    parser.add_argument("--low-rebound-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--high-rebound-threshold-kwh", type=float, default=1_500_000.0)
    parser.add_argument("--tau-values", default="2,4,8,12")
    parser.add_argument("--duration-values", default="1,4,8,24")
    args = parser.parse_args()
    summary = plan_upper_only_boundary_truth(
        dataset_dir=args.dataset_dir,
        model_dir=args.model_dir,
        output_dir=args.output_dir,
        daily_diagnostic_subdir=args.daily_diagnostic_subdir,
        trigger_contract_subdir=args.trigger_contract_subdir,
        trigger_classifier=args.trigger_classifier,
        trigger_magnitude=args.trigger_magnitude,
        low_rebound_threshold_kwh=float(args.low_rebound_threshold_kwh),
        high_rebound_threshold_kwh=float(args.high_rebound_threshold_kwh),
        tau_values=tuple(int(value) for value in str(args.tau_values).split(",") if value.strip()),
        duration_values=tuple(int(value) for value in str(args.duration_values).split(",") if value.strip()),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
