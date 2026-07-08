from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from Data.thermal_archetypes.Vienna.calibrated_v1 import build_calibrated_v1_values
from dispatch.metrics import compute_thermflex_series_metrics
from Learning.datasets.save_dataset import save_dataset
from Learning.registry.register_dataset import register_dataset
from Learning.thermflex_hourly_mechanism.schema import (
    BUILDER_METADATA_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    ENGINEERED_FEATURE_COLUMNS,
    MECHANISM_CORE_EVENT_TARGET_COLUMNS,
    MECHANISM_CORE_TARGET_COLUMNS,
    MECHANISM_ENERGY_TARGET_COLUMNS,
    MECHANISM_ENERGY_INTENSIVE_TARGET_COLUMNS,
    MECHANISM_ENERGY_STATE_INTENSIVE_TARGET_COLUMNS,
    REQUIRED_HOURLY_MECHANISM_COLUMNS,
    TARGET_COLUMNS,
    THERMAL_ARCHETYPE_FEATURE_COLUMNS,
    validate_hourly_mechanism_frame,
)
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context
from Settings import get_settings

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "Learning" / "registry" / "registry.json"
_DEFAULT_HOURLY_GLOB_ROOT = Path(__file__).resolve().parents[2] / "Optimization" / "run" / "results" / "Vienna" / "gold"
_DEFAULT_OVERRIDE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
_HOURLY_TRUTH_FILENAMES: tuple[str, ...] = (
    "constant_thermflex_cohort_utilization_hourly.csv",
    "thermflex_cohort_utilization_hourly.csv",
)


@dataclass(frozen=True)
class CuratedDatasetResult:
    family_hash: str
    dataset_id: str
    dataset_root: Path
    truth_rows: int
    selected_rows: int
    selected_bundle_count: int


def discover_hourly_truth_csvs(*, source_root: Path = _DEFAULT_HOURLY_GLOB_ROOT) -> list[Path]:
    root = Path(source_root).resolve()
    matches: list[Path] = []
    for filename in _HOURLY_TRUTH_FILENAMES:
        matches.extend(root.rglob(filename))
    matches = sorted({path.resolve() for path in matches})
    if not matches:
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] no supported hourly cohort-utilization truth file "
            f"found under {root}; expected one of {list(_HOURLY_TRUTH_FILENAMES)}"
        )
    return matches


def load_hourly_mechanism_truth_table(*, hourly_csv_paths: list[Path]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for csv_path_like in hourly_csv_paths:
        csv_path = Path(csv_path_like).resolve()
        raw_df = pd.read_csv(csv_path)
        validate_hourly_mechanism_frame(raw_df, source_label=str(csv_path))
        df = raw_df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise")
        df["source_bundle_name"] = csv_path.parent.name
        df["source_hourly_csv"] = str(csv_path)
        rows.append(df)
    if not rows:
        raise ValueError("[thermflex_hourly_mechanism] no hourly truth rows loaded.")
    combined = pd.concat(rows, ignore_index=True)
    combined = combined.sort_values(["source_bundle_name", "case_label", "cohort_key", "timestamp"]).reset_index(drop=True)
    combined = _deduplicate_hourly_truth(combined)
    combined = _enrich_with_run_policy_context(combined)
    combined = _enrich_with_canonical_hourly_context(combined)
    combined["hour_of_day"] = combined["timestamp"].dt.hour.astype(int)
    combined["day_of_year"] = combined["timestamp"].dt.dayofyear.astype(int)
    combined["month"] = combined["timestamp"].dt.month.astype(int)
    combined["split_group_run"] = combined["run_dir"].astype(str)
    combined["split_group_case"] = combined["case_label"].astype(str)
    combined["split_group_bundle"] = combined["source_bundle_name"].astype(str)
    combined = _add_group_split_strata(combined)
    return combined


def export_curated_hourly_mechanism_dataset(
    *,
    source_root: Path = _DEFAULT_HOURLY_GLOB_ROOT,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    target_profile: str = "mechanism_core",
    family_slice: str = "all",
    feature_mode: str = "full",
) -> CuratedDatasetResult:
    truth = load_hourly_mechanism_truth_table(hourly_csv_paths=discover_hourly_truth_csvs(source_root=source_root))
    selected = _apply_family_slice(truth, family_slice=family_slice)
    selected = add_engineered_feature_columns(selected)
    target_columns = _resolve_target_profile(target_profile)
    numeric_feature_columns = _resolved_numeric_feature_columns(feature_mode=feature_mode)
    categorical_feature_columns = _resolved_categorical_feature_columns(feature_mode=feature_mode)
    x_numeric = selected.loc[:, list(numeric_feature_columns)].copy()
    x_encoded = pd.get_dummies(
        selected.loc[:, list(numeric_feature_columns) + list(categorical_feature_columns)].copy(),
        columns=list(categorical_feature_columns),
        dtype=float,
    )
    y_df = selected.loc[:, list(target_columns)].apply(pd.to_numeric, errors="raise")

    family_spec = {
        "dataset_kind": "thermflex_hourly_mechanism_curated",
        "schema_version": "thermflex_hourly_mechanism_v1",
        "target_profile": target_profile,
        "family_slice": family_slice,
        "feature_mode": feature_mode,
        "source_hourly_csvs": [str(path) for path in discover_hourly_truth_csvs(source_root=source_root)],
        "selected_bundle_signatures": _selected_bundle_signatures(selected),
    }
    family_hash = _hash_family_spec(family_spec)
    dataset_id = f"thermflex_hourly_mechanism_{family_hash[:12]}"
    meta = {
        "dataset_kind": "thermflex_hourly_mechanism_curated",
        "family_hash": family_hash,
        "dataset_id": dataset_id,
        "n_truth_rows_total": int(len(truth)),
        "n_selected_rows": int(len(selected)),
        "n_selected_bundles": int(selected["source_bundle_name"].nunique()),
        "family_slice": family_slice,
        "feature_mode": feature_mode,
        "feature_columns": list(numeric_feature_columns),
        "categorical_feature_columns": list(categorical_feature_columns),
        "encoded_feature_columns": [str(col) for col in x_encoded.columns],
        "target_columns": list(target_columns),
        "group_columns": ["split_group_run", "split_group_case", "split_group_bundle"],
    }
    dataset_info = save_dataset(
        dataset_root,
        family_hash,
        x_numeric.to_numpy(dtype=float),
        x_encoded.to_numpy(dtype=float),
        y_df.to_numpy(dtype=float),
        meta,
        bounds_names=list(numeric_feature_columns),
        target_names=list(target_columns),
        family_spec=family_spec,
        source_runs=_source_runs_manifest(selected),
    )
    truth_csv_path = Path(dataset_info["truth_csv_path"])
    truth_meta_path = Path(dataset_info["truth_meta_path"])
    selected.to_csv(truth_csv_path, index=False)
    truth_meta_path.write_text(
        json.dumps(
            {
                "dataset_kind": "thermflex_hourly_mechanism_curated_truth",
                "family_hash": family_hash,
                "dataset_id": dataset_id,
                "family_slice": family_slice,
                "feature_mode": feature_mode,
                "rows_after_selection": int(len(selected)),
                "selected_bundle_names": sorted(selected["source_bundle_name"].astype(str).unique().tolist()),
                "raw_columns": list(selected.columns),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_dataset(
        settings_stub,
        family_hash,
        dataset_id,
        {
            "source": "thermflex_hourly_mechanism_curated",
            "artifact_path": str(dataset_info["data_path"]),
            "meta_path": str(dataset_info["meta_path"]),
            "truth_csv_path": str(dataset_info["truth_csv_path"]),
            "truth_meta_path": str(dataset_info["truth_meta_path"]),
            "family_spec_path": str(dataset_info["family_spec_path"]) if dataset_info["family_spec_path"] else "",
            "source_runs_path": str(dataset_info["source_runs_path"]) if dataset_info["source_runs_path"] else "",
            "n_samples": int(len(selected)),
            "n_truth_rows_total": int(len(truth)),
            "is_active": True,
        },
    )
    return CuratedDatasetResult(
        family_hash=family_hash,
        dataset_id=dataset_id,
        dataset_root=Path(dataset_info["root"]),
        truth_rows=int(len(truth)),
        selected_rows=int(len(selected)),
        selected_bundle_count=int(selected["source_bundle_name"].nunique()),
    )


def add_engineered_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    required = {
        "cohort_floor_area_m2",
        "hour_of_day",
        "day_of_year",
        "irradiance_proxy",
        "solargains_proxy",
        "dh_space_heat_kwh",
        "dh_total_kwh",
        "space_heat_kwh",
        "day_setpoint_c",
        "night_setpoint_c",
        "thermflex_day_lower_bound_c",
        "thermflex_night_lower_bound_c",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] engineered features missing required source columns: "
            + ", ".join(missing)
        )
    hour_of_day = pd.to_numeric(df["hour_of_day"], errors="raise").to_numpy(dtype=float)
    day_of_year = pd.to_numeric(df["day_of_year"], errors="raise").to_numpy(dtype=float)
    dh_space = pd.to_numeric(df["dh_space_heat_kwh"], errors="raise").to_numpy(dtype=float)
    dh_total = pd.to_numeric(df["dh_total_kwh"], errors="raise").to_numpy(dtype=float)
    irr = pd.to_numeric(df["irradiance_proxy"], errors="raise").to_numpy(dtype=float)
    gains = pd.to_numeric(df["solargains_proxy"], errors="raise").to_numpy(dtype=float)
    space_heat = pd.to_numeric(df["space_heat_kwh"], errors="raise").to_numpy(dtype=float)
    if np.any(dh_space < 0.0) or np.any(dh_total < 0.0):
        raise ValueError("[thermflex_hourly_mechanism] engineered features require nonnegative DH context.")
    df["hour_of_day_sin"] = np.sin((2.0 * np.pi * hour_of_day) / 24.0)
    df["hour_of_day_cos"] = np.cos((2.0 * np.pi * hour_of_day) / 24.0)
    df["day_of_year_sin"] = np.sin((2.0 * np.pi * day_of_year) / 365.0)
    df["day_of_year_cos"] = np.cos((2.0 * np.pi * day_of_year) / 365.0)
    df["irradiance_per_dh_space_heat"] = irr / np.maximum(dh_space, 1e-9)
    df["solargains_per_dh_space_heat"] = gains / np.maximum(dh_space, 1e-9)
    df["cohort_space_heat_share_of_dh"] = space_heat / np.maximum(dh_total, 1e-9)
    day_setpoint = pd.to_numeric(df["day_setpoint_c"], errors="raise").to_numpy(dtype=float)
    night_setpoint = pd.to_numeric(df["night_setpoint_c"], errors="raise").to_numpy(dtype=float)
    day_lower = pd.to_numeric(df["thermflex_day_lower_bound_c"], errors="raise").to_numpy(dtype=float)
    night_lower = pd.to_numeric(df["thermflex_night_lower_bound_c"], errors="raise").to_numpy(dtype=float)
    floor_area = pd.to_numeric(df["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
    if np.any(floor_area <= 0.0):
        raise ValueError("[thermflex_hourly_mechanism] cohort_floor_area_m2 must stay > 0 for intensive targets.")
    df["day_thermflex_temperature_band_k"] = day_setpoint - day_lower
    df["night_thermflex_temperature_band_k"] = night_setpoint - night_lower
    q_delta = pd.to_numeric(df["cohort_q_delta_kwh"], errors="raise").to_numpy(dtype=float)
    preheat = pd.to_numeric(df["cohort_preheat_extra_kwh"], errors="raise").to_numpy(dtype=float)
    cutback = pd.to_numeric(df["cohort_cutback_shed_kwh"], errors="raise").to_numpy(dtype=float)
    df["cohort_q_delta_wh_per_m2"] = (1000.0 * q_delta) / floor_area
    df["cohort_preheat_extra_wh_per_m2"] = (1000.0 * preheat) / floor_area
    df["cohort_cutback_shed_wh_per_m2"] = (1000.0 * cutback) / floor_area
    df = _attach_thermal_archetype_feature_columns(df)
    return df


def _add_group_split_strata(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach explicit group-level strata for balanced holdout diagnostics.

    The strata are not part of the feature contract. They only prevent tiny
    tau-specific datasets from producing accidental holdouts that contain only
    one rebound regime. We calculate them from the persisted truth profile so
    the split contract is reproducible and visible in `truth_dataset.csv`.
    """

    df = frame.copy()
    rows: list[dict[str, Any]] = []
    for (run_dir, day), group in df.groupby(["run_dir", df["timestamp"].dt.floor("D")], sort=True):
        q_ref = group.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = group.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        metrics = compute_thermflex_series_metrics(q_true, q_ref)
        rebound_kwh = float(metrics["thermflex_rebound_kwh"])
        month = int(pd.Timestamp(day).month)
        rows.append(
            {
                "run_dir": str(run_dir),
                "day": pd.Timestamp(day),
                "split_stratum_season": "winter" if month in {1, 2, 12} else "shoulder",
                "split_stratum_rebound_bin": _rebound_split_bin(rebound_kwh),
            }
        )
    strata = pd.DataFrame(rows)
    strata["split_stratum_season_rebound"] = (
        strata["split_stratum_season"].astype(str)
        + "_"
        + strata["split_stratum_rebound_bin"].astype(str)
    )
    strata["split_stratum_season_rebound_active"] = (
        strata["split_stratum_season"].astype(str)
        + "_"
        + strata["split_stratum_rebound_bin"].map(lambda value: "low" if value == "low" else "active")
    )
    df["day"] = df["timestamp"].dt.floor("D")
    out = df.merge(strata, on=["run_dir", "day"], how="left", validate="many_to_one")
    if out["split_stratum_season_rebound_active"].isna().any():
        raise ValueError("[thermflex_hourly_mechanism] failed to attach split strata to all hourly rows.")
    out = out.drop(columns=["day"])
    return out


def _rebound_split_bin(rebound_kwh: float) -> str:
    """Return a coarse, stable daily rebound bin for grouped split balancing."""

    value = float(rebound_kwh)
    if value < 250_000.0:
        return "low"
    if value < 1_250_000.0:
        return "mid"
    return "high"


def _attach_thermal_archetype_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach calibrated EnergyPlus-side archetype descriptors.

    This block tests whether hourly mechanism errors are driven by physical
    envelope, thermal-mass and event-response parameters that are only implied
    by `cohort_key` in the default feature contract. All values come from the
    calibrated Vienna archetype SSOT; missing cohort coverage fails immediately.
    """

    df = frame.copy()
    archetypes = build_calibrated_v1_values()["archetypes"]
    if not isinstance(archetypes, dict) or not archetypes:
        raise ValueError("[thermflex_hourly_mechanism] calibrated archetype SSOT is empty.")

    period_rank = {"pre1975": 0.0, "1975_1990": 1.0, "1990_2000": 2.0, "2000_2014": 3.0}
    records: dict[str, dict[str, float]] = {}
    for cohort_key, payload in archetypes.items():
        if not isinstance(payload, dict):
            raise TypeError(
                "[thermflex_hourly_mechanism] calibrated archetype payload must be a dict for "
                f"{cohort_key}."
            )
        reduced = _required_nested_mapping(payload, "calibration_v1", "reduced_order_v1", context_label=str(cohort_key))
        event = _required_nested_mapping(payload, "calibration_v1", "event_response_v1", context_label=str(cohort_key))
        construction_period = str(payload["construction_period"])
        if construction_period not in period_rank:
            raise ValueError(
                "[thermflex_hourly_mechanism] unsupported archetype construction_period "
                f"'{construction_period}' for {cohort_key}."
            )
        sector = str(payload["sector"])
        if sector not in {"residential", "non_residential"}:
            raise ValueError(
                "[thermflex_hourly_mechanism] unsupported archetype sector "
                f"'{sector}' for {cohort_key}."
            )
        records[str(cohort_key)] = {
            "archetype_is_residential": 1.0 if sector == "residential" else 0.0,
            "archetype_construction_period_rank": float(period_rank[construction_period]),
            "archetype_u_wall_w_per_m2k": _required_numeric(payload, "u_wall", context_label=str(cohort_key)),
            "archetype_u_window_w_per_m2k": _required_numeric(payload, "u_window", context_label=str(cohort_key)),
            "archetype_u_roof_w_per_m2k": _required_numeric(payload, "u_roof", context_label=str(cohort_key)),
            "archetype_u_floor_w_per_m2k": _required_numeric(payload, "u_floor", context_label=str(cohort_key)),
            "archetype_wall_area_per_gfa": _required_numeric(payload, "wall_area_per_gfa", context_label=str(cohort_key)),
            "archetype_window_area_per_gfa": _required_numeric(payload, "window_area_per_gfa", context_label=str(cohort_key)),
            "archetype_roof_area_per_gfa": _required_numeric(payload, "roof_area_per_gfa", context_label=str(cohort_key)),
            "archetype_floor_exposed_per_gfa": _required_numeric(payload, "floor_exposed_per_gfa", context_label=str(cohort_key)),
            "archetype_conditioned_floor_share_of_gfa": _required_numeric(payload, "conditioned_floor_share_of_gfa", context_label=str(cohort_key)),
            "archetype_c_th_wh_per_m2k": _required_numeric(payload, "c_th_wh_per_m2k", context_label=str(cohort_key)),
            "archetype_t_min_c": _required_numeric(payload, "t_min_k", context_label=str(cohort_key)) - 273.15,
            "archetype_t_max_c": _required_numeric(payload, "t_max_k", context_label=str(cohort_key)) - 273.15,
            "archetype_fitted_total_loss_w_per_k": _required_numeric(reduced, "fitted_total_loss_coefficient_w_per_k", context_label=str(cohort_key)),
            "archetype_fitted_transmission_loss_w_per_k": _required_numeric(reduced, "fitted_transmission_loss_coefficient_w_per_k", context_label=str(cohort_key)),
            "archetype_fitted_infiltration_loss_w_per_k": _required_numeric(reduced, "fitted_infiltration_loss_coefficient_w_per_k_approx", context_label=str(cohort_key)),
            "archetype_fitted_effective_heat_capacity_wh_per_k": _required_numeric(reduced, "fitted_effective_heat_capacity_wh_per_k", context_label=str(cohort_key)),
            "archetype_fitted_tau_h": _required_numeric(reduced, "fitted_tau_h", context_label=str(cohort_key)),
            "archetype_fitted_total_loss_w_per_m2k": _required_numeric(reduced, "fitted_total_loss_coefficient_w_per_m2k", context_label=str(cohort_key)),
            "archetype_fitted_effective_heat_capacity_wh_per_m2k": _required_numeric(reduced, "fitted_effective_heat_capacity_wh_per_m2k", context_label=str(cohort_key)),
            "archetype_preheat_added_energy_kwh": _required_numeric(event, "preheat_added_energy_kwh", context_label=str(cohort_key)),
            "archetype_preheat_peak_excess_kw": _required_numeric(event, "preheat_peak_excess_kw", context_label=str(cohort_key)),
            "archetype_cutback_shed_energy_kwh": _required_numeric(event, "cutback_shed_energy_kwh", context_label=str(cohort_key)),
            "archetype_cutback_peak_shed_kw": _required_numeric(event, "cutback_peak_shed_kw", context_label=str(cohort_key)),
            "archetype_recovery_rebound_energy_kwh": _required_numeric(event, "recovery_rebound_energy_kwh", context_label=str(cohort_key)),
            "archetype_recovery_peak_rebound_kw": _required_numeric(event, "recovery_peak_rebound_kw", context_label=str(cohort_key)),
            "archetype_recovery_time_to_reference_h": _required_numeric(event, "recovery_time_to_reference_h", context_label=str(cohort_key)),
        }

    unknown_keys = sorted(set(df["cohort_key"].astype(str).unique()).difference(records))
    if unknown_keys:
        raise KeyError(
            "[thermflex_hourly_mechanism] calibrated archetype features missing cohort keys: "
            + ", ".join(unknown_keys)
        )
    feature_df = pd.DataFrame.from_dict(records, orient="index")
    feature_df.index.name = "cohort_key"
    enriched = df.merge(feature_df.reset_index(), on="cohort_key", how="left", validate="many_to_one")
    missing_feature_columns = [column for column in THERMAL_ARCHETYPE_FEATURE_COLUMNS if enriched[column].isna().any()]
    if missing_feature_columns:
        raise ValueError(
            "[thermflex_hourly_mechanism] calibrated archetype feature enrichment produced missing values: "
            + ", ".join(missing_feature_columns)
        )
    return enriched


def _required_nested_mapping(
    payload: dict[str, Any],
    first_key: str,
    second_key: str,
    *,
    context_label: str,
) -> dict[str, Any]:
    first = payload.get(first_key)
    if not isinstance(first, dict):
        raise KeyError(
            "[thermflex_hourly_mechanism] calibrated archetype missing mapping "
            f"`{first_key}` for {context_label}."
        )
    second = first.get(second_key)
    if not isinstance(second, dict):
        raise KeyError(
            "[thermflex_hourly_mechanism] calibrated archetype missing mapping "
            f"`{first_key}.{second_key}` for {context_label}."
        )
    return second


def _required_numeric(payload: dict[str, Any], key: str, *, context_label: str) -> float:
    if key not in payload:
        raise KeyError(
            "[thermflex_hourly_mechanism] calibrated archetype missing numeric field "
            f"`{key}` for {context_label}."
        )
    value = float(payload[key])
    if not np.isfinite(value):
        raise ValueError(
            "[thermflex_hourly_mechanism] calibrated archetype field must be finite: "
            f"`{key}` for {context_label}."
        )
    return value


def _deduplicate_hourly_truth(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Keep the newest bundle copy when older paper bundles contain the same truth row.

    The paper-dispatch-comparison folders contain overlapping cohort-utilization
    exports. Some older folders also use a different display `case_label` for
    the same physical `run_dir`; the deduplication key therefore uses the run,
    cohort and timestamp identity instead of the label text.
    """

    key_columns = ["run_dir", "cohort_key", "timestamp"]
    compare_columns = [
        column
        for column in REQUIRED_HOURLY_MECHANISM_COLUMNS
        if column not in {"case_label", "run_dir", "timestamp", "cohort_key"}
    ]
    duplicate_mask = frame.duplicated(subset=key_columns, keep=False)
    if duplicate_mask.any():
        conflicts: list[dict[str, Any]] = []
        for key, group in frame.loc[duplicate_mask].groupby(key_columns, sort=True):
            numeric = group.loc[:, compare_columns].apply(pd.to_numeric, errors="raise").astype(float)
            spread = numeric.max(axis=0) - numeric.min(axis=0)
            conflict_columns = [column for column, value in spread.items() if float(abs(value)) > 1e-9]
            if conflict_columns:
                conflicts.append(
                    {
                        "run_dir": str(key[0]),
                        "cohort_key": str(key[1]),
                        "timestamp": str(pd.Timestamp(key[2])),
                        "source_bundle_names": sorted(group["source_bundle_name"].astype(str).unique().tolist()),
                        "conflict_columns": conflict_columns[:20],
                    }
                )
        if conflicts:
            raise ValueError(
                "[thermflex_hourly_mechanism] duplicate hourly truth rows disagree; examples="
                + json.dumps(conflicts[:10], default=str)
            )

    deduped = frame.copy()
    deduped["_bundle_rank"] = deduped["source_bundle_name"].astype(str)
    deduped = deduped.sort_values(
        ["case_label", "run_dir", "cohort_key", "timestamp", "_bundle_rank"],
        ascending=[True, True, True, True, True],
    )
    deduped = deduped.drop_duplicates(
        subset=key_columns,
        keep="last",
    ).reset_index(drop=True)
    return deduped.drop(columns="_bundle_rank")


@lru_cache(maxsize=1)
def _canonical_hourly_context_long() -> pd.DataFrame:
    context = load_vienna_dh_thermflex_full_year_context()
    rows: list[pd.DataFrame] = []
    for cohort_key, frame in context.member_hourly_frames.items():
        current = frame.loc[
            :,
            [
                "timestamp",
                "space_heat_kwh",
                "hotwater_kwh",
                "dh_space_heat_kwh",
                "dh_total_kwh",
                "t_outdoor_c",
                "irradiance_proxy",
                "solargains_proxy",
                "mc_auction_eur_mwh",
                "gas_price_eur_mwh_fuel",
                "co2_price_eur_tco2",
            ],
        ].copy()
        current["cohort_key"] = str(cohort_key)
        rows.append(current)
    if not rows:
        raise ValueError("[thermflex_hourly_mechanism] canonical hourly context has no cohort frames.")
    combined = pd.concat(rows, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], errors="raise")
    return combined


def _enrich_with_canonical_hourly_context(df: pd.DataFrame) -> pd.DataFrame:
    context = _canonical_hourly_context_long()
    enriched = df.merge(
        context,
        on=["timestamp", "cohort_key"],
        how="left",
        validate="many_to_one",
    )
    required_context_columns = [
        "space_heat_kwh",
        "hotwater_kwh",
        "dh_space_heat_kwh",
        "dh_total_kwh",
        "t_outdoor_c",
        "irradiance_proxy",
        "solargains_proxy",
        "mc_auction_eur_mwh",
        "gas_price_eur_mwh_fuel",
        "co2_price_eur_tco2",
    ]
    missing = [column for column in required_context_columns if enriched[column].isna().any()]
    if missing:
        raise ValueError(
            "[thermflex_hourly_mechanism] canonical hourly-context enrichment missing columns: "
            + ", ".join(sorted(missing))
        )
    return enriched


@lru_cache(maxsize=64)
def _run_policy_context_for_run_dir(run_dir: str) -> dict[str, Any]:
    """Resolve explicit run-policy descriptors from the thermflex override SSOT.

    The hourly mechanism surrogate must distinguish `constant` vs `day_night`
    and related policy structure explicitly. We therefore do not guess from
    labels alone. Instead we map each replayed run back to its override slug and
    read the policy descriptors from the same override SSOT used by the run.
    """

    run_dir_path = Path(str(run_dir).strip()).resolve()
    run_name = run_dir_path.name
    if run_name.startswith("_replay_"):
        replay_slug = run_name[len("_replay_") :]
        replay_suffix = "_mechanism"
        if not replay_slug.endswith(replay_suffix):
            raise ValueError(
                "[thermflex_hourly_mechanism] synthetic replay run_dir must end with `_mechanism`: "
                f"{run_dir_path}"
            )
        core = replay_slug[: -len(replay_suffix)]
        if len(core) <= 9 or core[-9] != "_" or not core[-8:].isdigit():
            raise ValueError(
                "[thermflex_hourly_mechanism] synthetic replay run_dir must end with `_YYYYMMDD_mechanism`: "
                f"{run_dir_path}"
            )
        override_slug = core[:-9]
    else:
        if len(run_name) <= 16 or run_name[8] != "_" or run_name[15] != "_":
            raise ValueError(
                "[thermflex_hourly_mechanism] cannot normalize override slug from run_dir: "
                f"{run_dir_path}"
            )
        override_slug = run_name[16:]
    override_path = _DEFAULT_OVERRIDE_ROOT / f"{override_slug}.json"
    if not override_path.exists():
        scenario_suffixes = (
            "_peak_",
            "_price_",
            "_sunny_",
            "_wintertyp_",
            "_shouldertyp_",
        )
        resolved = None
        for marker in scenario_suffixes:
            if marker not in override_slug:
                continue
            prefix, suffix = override_slug.rsplit(marker, 1)
            if len(suffix) != 8 or not suffix.isdigit():
                raise FileNotFoundError(
                    "[thermflex_hourly_mechanism] scenario-tagged run_dir has an unsupported override suffix: "
                    f"{run_dir_path}"
                )
            candidate = _DEFAULT_OVERRIDE_ROOT / f"{prefix}.json"
            if candidate.exists():
                resolved = candidate
                break
            raise FileNotFoundError(
                "[thermflex_hourly_mechanism] scenario-tagged run_dir resolved to missing base override "
                f"{candidate} for {run_dir_path}"
            )
        if resolved is None:
            raise FileNotFoundError(
                "[thermflex_hourly_mechanism] override JSON not found for run_dir "
                f"{run_dir_path}: {override_path}"
            )
        override_path = resolved
    settings = get_settings(overrides=json.loads(override_path.read_text(encoding="utf-8-sig")))
    heating = settings.heating_control
    thermflex = settings.constraints.thermflex
    dispatch_cfg = settings.dispatch
    dispatch_contract = _dispatch_solve_contract(
        dispatch_cfg=dispatch_cfg,
        context_label=f"dispatch settings for {run_dir_path.name}",
    )
    return {
        "control_mode": str(getattr(heating, "control_mode", "")),
        "reference_control_mode": str(getattr(heating, "reference_control_mode", "")),
        "policy_tau_h": _required_float_attr(
            dispatch_cfg,
            "dh_bus_inertia_tau_h",
            context_label=f"dispatch settings for {run_dir_path.name}",
        ),
        **dispatch_contract,
        "constant_setpoint_c": float(getattr(heating, "constant_setpoint_c", 0.0) or 0.0),
        "day_setpoint_c": float(getattr(heating, "day_setpoint_c", 0.0) or 0.0),
        "night_setpoint_c": float(getattr(heating, "night_setpoint_c", 0.0) or 0.0),
        "thermflex_day_lower_bound_c": float(getattr(thermflex, "day_lower_bound_c", 0.0) or 0.0),
        "thermflex_night_lower_bound_c": float(getattr(thermflex, "night_lower_bound_c", 0.0) or 0.0),
        "thermflex_use_event_response_bounds": int(
            bool(getattr(thermflex, "use_event_response_bounds", False))
        ),
        "thermflex_enforce_event_peak_bounds": int(
            bool(getattr(thermflex, "enforce_event_peak_bounds", False))
        ),
        "thermflex_enforce_event_energy_bounds": int(
            bool(getattr(thermflex, "enforce_event_energy_bounds", False))
        ),
        "thermflex_enforce_recovery_cooldown": int(
            bool(getattr(thermflex, "enforce_recovery_cooldown", False))
        ),
        "thermflex_constrain_upper_temperature": int(
            bool(getattr(thermflex, "constrain_upper_temperature", False))
        ),
    }


def _enrich_with_run_policy_context(df: pd.DataFrame) -> pd.DataFrame:
    run_dirs = sorted(df["run_dir"].astype(str).unique().tolist())
    rows = []
    for run_dir in run_dirs:
        payload = _run_policy_context_for_run_dir(run_dir)
        payload["run_dir"] = str(run_dir)
        rows.append(payload)
    policy_df = pd.DataFrame(rows)
    enriched = df.merge(policy_df, on="run_dir", how="left", validate="many_to_one")
    required_columns = [
        "control_mode",
        "reference_control_mode",
        "policy_tau_h",
        "policy_dispatch_horizon_h",
        "policy_dispatch_rolling_commit_h",
        "policy_dispatch_lookahead_h",
        "policy_dispatch_is_rolling",
        "constant_setpoint_c",
        "day_setpoint_c",
        "night_setpoint_c",
        "thermflex_day_lower_bound_c",
        "thermflex_night_lower_bound_c",
        "thermflex_use_event_response_bounds",
        "thermflex_enforce_event_peak_bounds",
        "thermflex_enforce_event_energy_bounds",
        "thermflex_enforce_recovery_cooldown",
        "thermflex_constrain_upper_temperature",
    ]
    missing = [column for column in required_columns if enriched[column].isna().any()]
    if missing:
        raise ValueError(
            "[thermflex_hourly_mechanism] run-policy enrichment missing columns: "
            + ", ".join(sorted(missing))
        )
    return enriched


def _resolved_numeric_feature_columns(*, feature_mode: str = "full") -> tuple[str, ...]:
    """Return the explicit numeric feature contract for one hourly feature mode.

    We keep this selection explicit instead of ad-hoc notebook slicing because
    the dataset hash and downstream model comparison must encode which feature
    family was used. `evt24_compact` is intentionally narrow: once the policy
    family is already homogeneous, extra policy and market/solar context mostly
    adds noise rather than new mechanism signal.
    """

    mode = str(feature_mode).strip().lower()
    full_columns = (
        "cohort_member_count",
        "cohort_floor_area_m2",
        "thermflex_constant_lower_bound_c",
        "thermflex_max_flex_duration_h",
        "thermflex_max_events_per_day",
        "policy_tau_h",
        "policy_dispatch_horizon_h",
        "policy_dispatch_rolling_commit_h",
        "policy_dispatch_lookahead_h",
        "policy_dispatch_is_rolling",
        "constant_setpoint_c",
        "day_setpoint_c",
        "night_setpoint_c",
        "thermflex_day_lower_bound_c",
        "thermflex_night_lower_bound_c",
        "thermflex_use_event_response_bounds",
        "thermflex_enforce_event_peak_bounds",
        "thermflex_enforce_event_energy_bounds",
        "thermflex_enforce_recovery_cooldown",
        "thermflex_constrain_upper_temperature",
        "hour_of_day",
        "day_of_year",
        "month",
        "t_outdoor_c",
        "irradiance_proxy",
        "solargains_proxy",
        "mc_auction_eur_mwh",
        "gas_price_eur_mwh_fuel",
        "co2_price_eur_tco2",
        "space_heat_kwh",
        "hotwater_kwh",
        "dh_space_heat_kwh",
        "dh_total_kwh",
        "cohort_q_heat_ref_kwh",
    ) + tuple(ENGINEERED_FEATURE_COLUMNS)
    if mode == "full":
        return full_columns
    if mode == "full_thermal":
        return full_columns + tuple(THERMAL_ARCHETYPE_FEATURE_COLUMNS)
    if mode == "evt24_compact":
        return (
            "cohort_floor_area_m2",
            "hour_of_day",
            "day_of_year",
            "month",
            "policy_tau_h",
            "policy_dispatch_horizon_h",
            "policy_dispatch_rolling_commit_h",
            "policy_dispatch_lookahead_h",
            "policy_dispatch_is_rolling",
            "t_outdoor_c",
            "dh_space_heat_kwh",
            "dh_total_kwh",
            "cohort_q_heat_ref_kwh",
            "hour_of_day_sin",
            "hour_of_day_cos",
            "day_of_year_sin",
            "day_of_year_cos",
        )
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported feature mode: {feature_mode}")


def _resolved_categorical_feature_columns(*, feature_mode: str = "full") -> tuple[str, ...]:
    """Return the explicit categorical feature contract for one hourly mode."""

    mode = str(feature_mode).strip().lower()
    if mode in {"full", "full_thermal"}:
        return tuple(CATEGORICAL_FEATURE_COLUMNS)
    if mode == "evt24_compact":
        return ("cohort_key",)
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported feature mode: {feature_mode}")


def _required_float_attr(obj: Any, attr_name: str, *, context_label: str) -> float:
    """Read one required numeric settings attribute without silent fallback."""

    if not hasattr(obj, attr_name):
        raise AttributeError(
            "[thermflex_hourly_mechanism] required attribute "
            f"`{attr_name}` missing in {context_label}."
        )
    value = getattr(obj, attr_name)
    if value is None:
        raise ValueError(
            "[thermflex_hourly_mechanism] required attribute "
            f"`{attr_name}` is None in {context_label}."
        )
    return float(value)


def _dispatch_solve_contract(*, dispatch_cfg: Any, context_label: str) -> dict[str, float]:
    """Expose the MILP rolling-horizon contract as explicit hourly features."""

    horizon_h = _required_positive_int_attr(
        dispatch_cfg,
        "horizon_h",
        context_label=context_label,
    )
    rolling_commit_raw_h = _required_nonnegative_int_attr(
        dispatch_cfg,
        "rolling_commit_h",
        context_label=context_label,
    )
    rolling_commit_h = horizon_h if rolling_commit_raw_h <= 0 else rolling_commit_raw_h
    if rolling_commit_h > horizon_h:
        raise ValueError(
            "[thermflex_hourly_mechanism] dispatch rolling horizon contract invalid in "
            f"{context_label}: rolling_commit_h={rolling_commit_h}, horizon_h={horizon_h}."
        )
    lookahead_h = horizon_h - rolling_commit_h
    return {
        "policy_dispatch_horizon_h": float(horizon_h),
        "policy_dispatch_rolling_commit_h": float(rolling_commit_h),
        "policy_dispatch_lookahead_h": float(lookahead_h),
        "policy_dispatch_is_rolling": float(lookahead_h > 0),
    }


def _required_positive_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = _required_int_attr(obj, attr_name, context_label=context_label)
    if value <= 0:
        raise ValueError(
            "[thermflex_hourly_mechanism] required positive integer setting "
            f"`{attr_name}` must be > 0 in {context_label}, got {value}."
        )
    return value


def _required_nonnegative_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = _required_int_attr(obj, attr_name, context_label=context_label)
    if value < 0:
        raise ValueError(
            "[thermflex_hourly_mechanism] required nonnegative integer setting "
            f"`{attr_name}` must be >= 0 in {context_label}, got {value}."
        )
    return value


def _required_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    if not hasattr(obj, attr_name):
        raise AttributeError(
            "[thermflex_hourly_mechanism] required dispatch setting "
            f"`{attr_name}` missing in {context_label}."
        )
    value = getattr(obj, attr_name)
    if value is None:
        raise ValueError(
            "[thermflex_hourly_mechanism] required dispatch setting "
            f"`{attr_name}` is None in {context_label}."
        )
    return int(value)


def _apply_family_slice(frame: pd.DataFrame, *, family_slice: str) -> pd.DataFrame:
    """Keep hourly truth segmentation explicit and reproducible.

    We do not silently infer slices from labels in downstream notebooks. The
    dataset contract itself records which control-family slice was selected.
    """

    slice_name = str(family_slice).strip().lower()
    if slice_name == "all":
        return frame.copy()
    if slice_name == "constant_only":
        selected = frame.loc[frame["control_mode"].astype(str) == "constant"].copy()
    elif slice_name == "day_night_only":
        selected = frame.loc[frame["control_mode"].astype(str) == "day_night"].copy()
    elif slice_name == "constant_evt1_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 1)
        ].copy()
    elif slice_name == "constant_evt24_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
        ].copy()
    elif slice_name == "constant_evt1_lower_relax_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 1)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_dur4_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & (pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise") == 4)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau0_only":
        # Keep the historical lower-relax regime explicit.
        #
        # Why this slice exists:
        # - older lower-relax replay/mechanism truth was built before the tau
        #   sensitivity work and therefore carries `policy_tau_h == 0`,
        # - once real tau-sensitive truth (`3h`, `4h`, `5h`, `6h`, ...) enters
        #   the same slice, the model is otherwise asked to generalize across a
        #   hidden physical regime shift,
        # - this repo should not rely on the model to silently absorb that
        #   mismatch; the dataset contract must expose it.
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(pd.to_numeric(frame["policy_tau_h"], errors="raise"), 0.0)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau3_4_only":
        # Keep the first real tau-sensitive lower-relax regime together.
        #
        # Why `3h` and `4h` are grouped:
        # - they currently have the densest tau-specific truth,
        # - they stay close to the operational `tau=4h` reference the user
        #   actually cares about,
        # - grouping them preserves enough holdout groups to make the first
        #   stability check meaningful.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & (np.isclose(tau, 3.0) | np.isclose(tau, 4.0))
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau3_only":
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 3.0)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau4_only":
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 4.0)
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau4_winter_only":
        # Keep the dense winter-heating tau4 regime separate from low-load
        # shoulder days.
        #
        # Why this slice exists:
        # - tau4 currently mixes January heavy-load days with March/April/October
        #   transition days,
        # - the shifted diagnostic already showed that these transition days can
        #   carry much larger shifted energy at far lower absolute DH load,
        # - if those two mechanics are materially different, the model should
        #   not be forced to learn them as one homogeneous family.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        month = pd.to_numeric(frame["month"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 4.0)
            & month.isin([1, 2, 12])
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau4_transition_only":
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        month = pd.to_numeric(frame["month"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 4.0)
            & month.isin([3, 4, 10, 11])
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau4_spring_only":
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        month = pd.to_numeric(frame["month"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 4.0)
            & month.isin([3, 4])
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau4_autumn_only":
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        month = pd.to_numeric(frame["month"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & np.isclose(tau, 4.0)
            & month.isin([10, 11])
        ].copy()
    elif slice_name == "constant_evt24_lower_relax_tau5plus_only":
        # Keep the higher-inertia exploratory tau regime separate.
        #
        # Why this is not merged into the `tau3_4` slice:
        # - the earlier shifted diagnostics already showed materially different
        #   error behavior once tau moves above the dense `3h/4h` regime,
        # - keeping `5h+` separate lets us check whether the model is failing
        #   because of sparse truth or because this really is a different
        #   mechanism family.
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") < 22.5)
            & (pd.to_numeric(frame["policy_tau_h"], errors="raise") >= 5.0)
        ].copy()
    elif slice_name == "constant_evt24_lower1k_dur4_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") == 21.5)
            & (pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise") == 4)
        ].copy()
    elif slice_name == "constant_evt24_lower2k_dur4_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") == 20.5)
            & (pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise") == 4)
        ].copy()
    elif slice_name == "constant_evt24_upper_only":
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
        ].copy()
    elif slice_name == "constant_evt24_upper_only_tau4_only":
        # Keep real tau-sensitive upper-only truth separate from older
        # upper-only replay artifacts that were produced before tau was part of
        # the explicit learning contract and therefore carry `policy_tau_h == 0`.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
            & np.isclose(tau, 4.0)
        ].copy()
    elif slice_name == "constant_upper_only_tau4_duration_family":
        # Keep the tau4 upper-only duration family explicit.
        #
        # The older upper-only paper slice is intentionally `evt24`-only.  The
        # boundary truth added for rebound diagnostics uses the matching
        # `evt == duration` contracts for dur1/dur4/dur8, so filtering by
        # `evt24` would silently discard the very cases that are meant to teach
        # the duration router.  This slice groups the duration contracts by the
        # physical policy knobs that define the current family: constant
        # upper-only control, real tau4 truth, and the supported paper
        # durations.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        duration = pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
            & np.isclose(tau, 4.0)
            & duration.isin([1, 4, 8, 24])
        ].copy()
    elif slice_name == "constant_upper_only_tau4_short_duration_only":
        # Isolate the newly added short-duration boundary truth.  This is useful
        # for checking whether dur1/dur4/dur8 have their own residual error
        # pattern before they are mixed into the broader dur1/4/8/24 family.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        duration = pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
            & np.isclose(tau, 4.0)
            & duration.isin([1, 4, 8])
        ].copy()
    elif slice_name == "constant_upper_only_evt24_tau_sensitivity":
        # Keep the paper-style dur24/evt24 contract while varying tau.
        #
        # This is the clean sensitivity-analysis family for larger tau values:
        # it excludes old upper-only artifacts with missing tau (`0`) and keeps
        # all rows on the same duration/event contract so tau effects are not
        # confounded with duration effects.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
            & (pd.to_numeric(frame["thermflex_max_events_per_day"], errors="raise") == 24)
            & (pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise") == 24)
            & tau.isin([2.0, 4.0, 8.0, 12.0])
        ].copy()
    elif slice_name == "constant_upper_only_tau_duration_family":
        # Full targeted sensitivity family: tau and duration both explicit.
        #
        # This slice is intentionally separate from the tau4 duration family.
        # It is meant for router/sensitivity diagnostics that include
        # `policy_tau_h` and `thermflex_max_flex_duration_h` as first-class
        # features, not for a single pooled dur24 production model.
        tau = pd.to_numeric(frame["policy_tau_h"], errors="raise")
        duration = pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise")
        selected = frame.loc[
            (frame["control_mode"].astype(str) == "constant")
            & (pd.to_numeric(frame["thermflex_constant_lower_bound_c"], errors="raise") >= 22.5)
            & tau.isin([2.0, 4.0, 8.0, 12.0])
            & duration.isin([1, 4, 8, 24])
        ].copy()
    else:
        raise ValueError(f"[thermflex_hourly_mechanism] unsupported family slice: {family_slice}")
    if selected.empty:
        raise ValueError(
            "[thermflex_hourly_mechanism] family slice produced no hourly truth rows: "
            f"{family_slice}"
        )
    return selected.reset_index(drop=True)


def _resolve_target_profile(target_profile: str) -> tuple[str, ...]:
    profile = str(target_profile).strip().lower()
    if profile == "all":
        return tuple(TARGET_COLUMNS)
    if profile == "mechanism_core":
        return tuple(MECHANISM_CORE_TARGET_COLUMNS)
    if profile == "mechanism_core_event":
        return tuple(MECHANISM_CORE_EVENT_TARGET_COLUMNS)
    if profile == "mechanism_energy":
        return tuple(MECHANISM_ENERGY_TARGET_COLUMNS)
    if profile == "mechanism_energy_intensive":
        return tuple(MECHANISM_ENERGY_INTENSIVE_TARGET_COLUMNS)
    if profile == "mechanism_energy_state_intensive":
        return tuple(MECHANISM_ENERGY_STATE_INTENSIVE_TARGET_COLUMNS)
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported target profile: {target_profile}")


def _selected_bundle_signatures(selected: pd.DataFrame) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    for bundle_name, bundle_df in selected.groupby("source_bundle_name", sort=True):
        signatures.append(
            {
                "bundle_name": str(bundle_name),
                "source_hourly_csv": str(bundle_df["source_hourly_csv"].iloc[0]),
                "rows": int(len(bundle_df)),
                "case_count": int(bundle_df["case_label"].nunique()),
                "cohort_count": int(bundle_df["cohort_key"].nunique()),
                "timestamp_count": int(bundle_df["timestamp"].nunique()),
            }
        )
    return signatures


def _source_runs_manifest(selected: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_dir, run_df in selected.groupby("run_dir", sort=True):
        rows.append(
            {
                "run_dir": str(run_dir),
                "case_label": str(run_df["case_label"].iloc[0]),
                "source_bundle_names": sorted(run_df["source_bundle_name"].astype(str).unique().tolist()),
                "row_count": int(len(run_df)),
                "timestamp_count": int(run_df["timestamp"].nunique()),
                "cohort_count": int(run_df["cohort_key"].nunique()),
            }
        )
    return rows


def _hash_family_spec(family_spec: dict[str, Any]) -> str:
    payload = json.dumps(family_spec, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
