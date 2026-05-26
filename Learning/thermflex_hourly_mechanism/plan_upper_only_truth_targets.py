from __future__ import annotations

"""Plan targeted upper-only truth days from existing screen artifacts.

The current upper-only bottleneck is no longer a generic hourly fit problem.
Diagnostics show two narrow failure modes: shoulder days where rebound is
active vs. almost zero, and winter old-building mass/timing days. This script
turns already persisted screen artifacts into an explicit target list for the
next truth collection batch, while marking which days are already present in
the current learning dataset.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = (
    REPO_ROOT
    / "Learning"
    / "datasets"
    / "6d058845d59b20453e43f83a1aec191c008683dee567ce9644a90d92d228a7fc"
)
DEFAULT_MODEL_DIR = (
    REPO_ROOT
    / "Learning"
    / "models"
    / "thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6d058845d59b_features_no_case_label_transforms_mechanism_mass_identity"
)
DEFAULT_SCREEN_ROOT = REPO_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "Learning"
    / "models"
    / "thermflex_hourly_mechanism_upper_only_truth_target_plan_6d058845d59b"
)


@dataclass(frozen=True)
class TargetSpec:
    """One deterministic selection rule for the target-plan CSV."""

    focus: str
    priority: int
    reason: str
    max_rows: int


TARGET_SPECS = (
    TargetSpec(
        focus="shoulder_zero_rebound_boundary",
        priority=10,
        reason=(
            "Shoulder zero/low rebound cases near active-rebound weather/load "
            "conditions; this is the observed false-activation boundary."
        ),
        max_rows=12,
    ),
    TargetSpec(
        focus="shoulder_high_rebound_boundary",
        priority=20,
        reason=(
            "Shoulder high-rebound cases paired with the zero-boundary days; "
            "needed so the gate learns both sides of the same regime."
        ),
        max_rows=12,
    ),
    TargetSpec(
        focus="winter_old_mass_timing",
        priority=30,
        reason=(
            "Cold winter/high-load days where old residential cohorts dominated "
            "the mass and timing error in the diagnostics."
        ),
        max_rows=12,
    ),
    TargetSpec(
        focus="high_rebound_tail",
        priority=40,
        reason=(
            "Upper tail of daily rebound; protects the active-regressor against "
            "systematic underprediction."
        ),
        max_rows=8,
    ),
    TargetSpec(
        focus="existing_holdout_failure_anchor",
        priority=90,
        reason=(
            "Already present holdout failure day; keep as anchor for routed "
            "evaluation and family-balanced splits, not as new truth demand."
        ),
        max_rows=20,
    ),
)


def plan_upper_only_truth_targets(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    screen_root: Path = DEFAULT_SCREEN_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    daily_diagnostic_subdir: str = "upper_only_subcontracts_enhanced",
) -> dict[str, Any]:
    """Create the inventory and prioritized target plan artifacts."""

    dataset_root = Path(dataset_dir).resolve()
    model_root = Path(model_dir).resolve()
    screen_root = Path(screen_root).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    inventory = _load_candidate_inventory(screen_root)
    truth_dates = _load_truth_dates(dataset_root)
    inventory["already_in_learning_dataset"] = inventory["date"].isin(truth_dates)

    diagnostics = _load_failure_diagnostics(model_root, daily_diagnostic_subdir=str(daily_diagnostic_subdir))
    target_plan = _build_target_plan(inventory=inventory, diagnostics=diagnostics)

    inventory_csv = output_root / "upper_only_screen_inventory.csv"
    target_csv = output_root / "upper_only_truth_target_plan.csv"
    summary_json = output_root / "upper_only_truth_target_summary.json"
    readme_path = output_root / "README.md"

    inventory.to_csv(inventory_csv, index=False)
    target_plan.to_csv(target_csv, index=False)

    summary: dict[str, Any] = {
        "dataset_dir": str(dataset_root),
        "model_dir": str(model_root),
        "screen_root": str(screen_root),
        "daily_diagnostic_subdir": str(daily_diagnostic_subdir),
        "inventory_rows": int(len(inventory)),
        "inventory_unique_dates": int(inventory["date"].nunique()),
        "inventory_dates_not_in_learning_dataset": int(
            (~inventory["already_in_learning_dataset"]).sum()
        ),
        "target_rows": int(len(target_plan)),
        "target_rows_new_truth": int(
            (target_plan["recommended_action"] == "add_truth_run").sum()
        ),
        "target_rows_existing_anchors": int(
            (target_plan["recommended_action"] == "keep_as_evaluation_anchor").sum()
        ),
        "targets_by_focus": target_plan["target_focus"].value_counts().to_dict(),
        "outputs": {
        "inventory_csv": str(inventory_csv),
            "target_csv": str(target_csv),
            "summary_json": str(summary_json),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    readme_path.write_text(_readme_text(summary), encoding="utf-8")
    return summary


def _load_candidate_inventory(screen_root: Path) -> pd.DataFrame:
    """Read upper-only dur24 screen/bundle CSVs and keep one row per date.

    The source folders remain the raw artifact SSOT. The inventory only points
    back to them and deduplicates identical dates for planning.
    """

    csv_paths = sorted(screen_root.glob("daily_thermflex_screen*upper_only*/heating_season_day_screen.csv"))
    csv_paths += sorted(screen_root.glob("paper_mechanism_bundle_upper*/selected_days.csv"))
    csv_paths += sorted(screen_root.glob("paper_mechanism_bundle_upper*/heating_season_screen_joined.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No upper-only daily candidate CSVs found below {screen_root}")

    frames: list[pd.DataFrame] = []
    for csv_path in csv_paths:
        frame = pd.read_csv(csv_path)
        if "flex_override_name" not in frame.columns:
            continue
        dur24_mask = frame["flex_override_name"].astype(str).str.contains("dur24", case=False, na=False)
        if not dur24_mask.any():
            continue

        required = [
            "date",
            "t_outdoor_mean_c",
            "t_outdoor_min_c",
            "dh_space_heat_total_kwh",
            "thermflex_shifted_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_peak_change_kw",
            "district_gas_boiler_peak_kw_delta",
            "flex_case_label",
            "flex_override_name",
        ]
        optional = [
            "district_gas_chp_thermal_generation_kwh_delta",
            "dispatch_heat_operating_cost_eur_delta",
            "dispatch_heat_allocated_co2_t_delta",
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"{csv_path} is missing required columns: {missing}")

        slim = frame.loc[dur24_mask, required].copy()
        for column in optional:
            if column in frame.columns:
                slim[column] = frame.loc[dur24_mask, column]
            else:
                slim[column] = np.nan
        slim["source_artifact_kind"] = (
            "screen_day_csv"
            if csv_path.name == "heating_season_day_screen.csv"
            else "bundle_screen_joined"
            if csv_path.name == "heating_season_screen_joined.csv"
            else "bundle_selected_days"
        )
        slim["source_screen_dir"] = csv_path.parent.name
        slim["source_screen_csv"] = str(csv_path)
        slim["source_mtime"] = csv_path.stat().st_mtime
        frames.append(slim)

    if not frames:
        raise ValueError(f"Upper-only daily candidate CSVs exist below {screen_root}, but none are dur24.")

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date.astype(str)
    numeric_columns = [
        "t_outdoor_mean_c",
        "t_outdoor_min_c",
        "dh_space_heat_total_kwh",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_peak_change_kw",
        "district_gas_boiler_peak_kw_delta",
        "district_gas_chp_thermal_generation_kwh_delta",
        "dispatch_heat_operating_cost_eur_delta",
        "dispatch_heat_allocated_co2_t_delta",
        "source_mtime",
    ]
    for column in numeric_columns:
        combined[column] = pd.to_numeric(combined[column], errors="raise")

    combined = combined.sort_values(["date", "source_mtime"], ascending=[True, False])
    source_join = (
        combined.groupby("date")["source_screen_dir"]
        .agg(lambda values: ";".join(dict.fromkeys(values.astype(str))))
        .rename("all_source_screen_dirs")
    )
    artifact_join = (
        combined.groupby("date")["source_artifact_kind"]
        .agg(lambda values: ";".join(dict.fromkeys(values.astype(str))))
        .rename("all_source_artifact_kinds")
    )
    deduped = combined.drop_duplicates("date", keep="first").merge(
        source_join, left_on="date", right_index=True, how="left"
    )
    deduped = deduped.merge(artifact_join, left_on="date", right_index=True, how="left")
    deduped["month"] = pd.to_datetime(deduped["date"]).dt.month
    deduped["season_regime"] = np.select(
        [deduped["month"].isin([12, 1, 2]), deduped["month"].isin([3, 4, 10, 11])],
        ["winter", "shoulder"],
        default="other",
    )
    deduped["rebound_active_screen"] = deduped["thermflex_rebound_kwh"] > 25_000.0
    return deduped.sort_values("date").reset_index(drop=True)


def _load_truth_dates(dataset_dir: Path) -> set[str]:
    """Return dates already represented in the current upper-only dataset."""

    truth_csv = dataset_dir / "truth_dataset.csv"
    if not truth_csv.exists():
        raise FileNotFoundError(f"Missing truth dataset: {truth_csv}")
    truth = pd.read_csv(truth_csv, usecols=["timestamp"])
    return set(pd.to_datetime(truth["timestamp"]).dt.date.astype(str))


def _load_failure_diagnostics(model_dir: Path, *, daily_diagnostic_subdir: str) -> pd.DataFrame:
    """Load the current holdout failure labels used as anchor rows."""

    diagnostics_csv = model_dir / "diagnostics" / str(daily_diagnostic_subdir) / "daily_rebound_gate_rows.csv"
    if not diagnostics_csv.exists():
        raise FileNotFoundError(f"Missing upper-only diagnostic CSV: {diagnostics_csv}")
    diagnostics = pd.read_csv(diagnostics_csv)
    required = [
        "day",
        "is_test",
        "season_regime",
        "failure_mode",
        "shifted_true_kwh",
        "rebound_true_kwh",
        "peak_true_kw",
        "q_ref_sum_kwh",
        "t_outdoor_mean_c",
    ]
    missing = [column for column in required if column not in diagnostics.columns]
    if missing:
        raise ValueError(f"{diagnostics_csv} is missing required columns: {missing}")
    diagnostics["day"] = pd.to_datetime(diagnostics["day"]).dt.date.astype(str)
    return diagnostics.loc[diagnostics["is_test"].astype(bool), required].copy()


def _build_target_plan(*, inventory: pd.DataFrame, diagnostics: pd.DataFrame) -> pd.DataFrame:
    """Apply explicit target rules and return a ranked, deduplicated plan."""

    pieces: list[pd.DataFrame] = []
    specs = {spec.focus: spec for spec in TARGET_SPECS}
    not_in_truth = inventory.loc[~inventory["already_in_learning_dataset"]].copy()

    # The rebound gate failed exactly in the shoulder zero-vs-high band. Keep
    # zero/low and high-active examples balanced so the next truth batch teaches
    # the boundary instead of only adding more high-rebound mass.
    shoulder_band = not_in_truth.loc[
        (not_in_truth["season_regime"] == "shoulder")
        & not_in_truth["t_outdoor_mean_c"].between(9.0, 16.0)
        & not_in_truth["dh_space_heat_total_kwh"].between(3_000_000.0, 22_000_000.0)
    ].copy()
    zero_boundary = shoulder_band.loc[shoulder_band["thermflex_rebound_kwh"] <= 250_000.0].copy()
    zero_boundary["boundary_score"] = (
        zero_boundary["t_outdoor_mean_c"].sub(13.0).abs()
        + zero_boundary["dh_space_heat_total_kwh"].sub(10_000_000.0).abs() / 10_000_000.0
    )
    pieces.append(
        _annotate(
            zero_boundary.sort_values("boundary_score").head(specs["shoulder_zero_rebound_boundary"].max_rows),
            specs["shoulder_zero_rebound_boundary"],
        )
    )

    high_boundary = shoulder_band.loc[shoulder_band["thermflex_rebound_kwh"] >= 1_500_000.0].copy()
    high_boundary["boundary_score"] = (
        high_boundary["t_outdoor_mean_c"].sub(13.0).abs()
        + high_boundary["dh_space_heat_total_kwh"].sub(10_000_000.0).abs() / 10_000_000.0
        - high_boundary["thermflex_rebound_kwh"] / 10_000_000.0
    )
    pieces.append(
        _annotate(
            high_boundary.sort_values("boundary_score").head(specs["shoulder_high_rebound_boundary"].max_rows),
            specs["shoulder_high_rebound_boundary"],
        )
    )

    # Winter high-load days mainly address old-cohort mass and timing. We do
    # not have the cohort split in the screen rows, so we use cold/high-load
    # daily cases as the stable screen-level proxy.
    winter_mass = not_in_truth.loc[
        (not_in_truth["season_regime"] == "winter")
        & (not_in_truth["t_outdoor_mean_c"] <= 5.5)
        & (not_in_truth["dh_space_heat_total_kwh"] >= 25_000_000.0)
    ].copy()
    winter_mass["winter_score"] = (
        -winter_mass["dh_space_heat_total_kwh"] / 10_000_000.0
        -winter_mass["thermflex_shifted_space_heat_kwh"] / 2_000_000.0
        + winter_mass["t_outdoor_mean_c"]
    )
    pieces.append(
        _annotate(
            winter_mass.sort_values("winter_score").head(specs["winter_old_mass_timing"].max_rows),
            specs["winter_old_mass_timing"],
        )
    )

    high_tail = not_in_truth.loc[not_in_truth["thermflex_rebound_kwh"] >= 2_500_000.0].copy()
    high_tail["tail_score"] = -high_tail["thermflex_rebound_kwh"]
    pieces.append(
        _annotate(
            high_tail.sort_values("tail_score").head(specs["high_rebound_tail"].max_rows),
            specs["high_rebound_tail"],
        )
    )

    # Existing holdout failure rows are retained as anchors; they should not be
    # counted as new truth, but they tell future evaluators which days must stay
    # visible in grouped/stratified diagnostics.
    failure_days = set(diagnostics.loc[diagnostics["failure_mode"] != "rebound_ok_or_small", "day"])
    anchors = inventory.loc[inventory["date"].isin(failure_days)].copy()
    anchors = anchors.merge(
        diagnostics[["day", "failure_mode", "rebound_true_kwh", "shifted_true_kwh", "peak_true_kw"]],
        left_on="date",
        right_on="day",
        how="left",
    )
    pieces.append(
        _annotate(
            anchors.sort_values(["failure_mode", "date"]).head(specs["existing_holdout_failure_anchor"].max_rows),
            specs["existing_holdout_failure_anchor"],
        )
    )

    plan = pd.concat([piece for piece in pieces if len(piece)], ignore_index=True)
    if plan.empty:
        raise ValueError("No target rows selected; inspect screen inventory and target rules.")

    plan["recommended_action"] = np.where(
        plan["already_in_learning_dataset"],
        "keep_as_evaluation_anchor",
        "add_truth_run",
    )
    plan["priority_rank"] = plan["target_priority"] * 10_000 + plan.groupby("target_focus").cumcount()
    output_columns = [
        "priority_rank",
        "recommended_action",
        "target_focus",
        "target_reason",
        "date",
        "season_regime",
        "t_outdoor_mean_c",
        "t_outdoor_min_c",
        "dh_space_heat_total_kwh",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_peak_change_kw",
        "district_gas_boiler_peak_kw_delta",
        "district_gas_chp_thermal_generation_kwh_delta",
        "dispatch_heat_operating_cost_eur_delta",
        "dispatch_heat_allocated_co2_t_delta",
        "already_in_learning_dataset",
        "source_artifact_kind",
        "source_screen_dir",
        "source_screen_csv",
        "all_source_screen_dirs",
        "all_source_artifact_kinds",
        "flex_case_label",
        "flex_override_name",
    ]
    optional = [column for column in ["failure_mode", "rebound_true_kwh", "shifted_true_kwh", "peak_true_kw"] if column in plan]
    plan = plan[output_columns + optional].sort_values(["priority_rank", "date"])

    # A date can be selected by several rules; keep the strongest priority but
    # retain the first clear rationale for the next run contract.
    return plan.drop_duplicates("date", keep="first").reset_index(drop=True)


def _annotate(frame: pd.DataFrame, spec: TargetSpec) -> pd.DataFrame:
    """Attach the rule metadata to selected rows."""

    if frame.empty:
        return frame
    annotated = frame.copy()
    annotated["target_focus"] = spec.focus
    annotated["target_priority"] = spec.priority
    annotated["target_reason"] = spec.reason
    return annotated


def _readme_text(summary: dict[str, Any]) -> str:
    """Document the generated planning folder as a reusable artifact."""

    return (
        "# Upper-only Truth Target Plan\n\n"
        "This folder contains a derived planning artifact for targeted upper-only "
        "truth collection. Raw run outputs remain in `Optimization/run/results/`; "
        "the CSVs here only inventory those sources and rank dates for the next "
        "learning dataset expansion.\n\n"
        "Key files:\n"
        "- `upper_only_screen_inventory.csv`: deduplicated dur24 upper-only screen days.\n"
        "- `upper_only_truth_target_plan.csv`: prioritized dates and rationale.\n"
        "- `upper_only_truth_target_summary.json`: source paths and counts.\n\n"
        f"Current target rows: {summary['target_rows']} "
        f"({summary['target_rows_new_truth']} new truth candidates, "
        f"{summary['target_rows_existing_anchors']} existing anchors).\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--screen-root", type=Path, default=DEFAULT_SCREEN_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--daily-diagnostic-subdir", default="upper_only_subcontracts_enhanced")
    args = parser.parse_args()
    summary = plan_upper_only_truth_targets(
        dataset_dir=args.dataset_dir,
        model_dir=args.model_dir,
        screen_root=args.screen_root,
        output_dir=args.output_dir,
        daily_diagnostic_subdir=args.daily_diagnostic_subdir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
