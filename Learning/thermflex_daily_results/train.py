from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.metrics import r2_score
from xgboost import XGBRegressor

from Learning.datasets.load_dataset import load_dataset
from Learning.datasets.load_dataset import validate_truth_row_alignment
from Learning.registry.register_model import register_model
from Learning.registry.update_model_status import update_model_status
from Learning.thermflex_daily_results.dataset_builder import (
    _DEFAULT_DATASET_ROOT,
    _DEFAULT_REGISTRY_PATH,
    export_curated_daily_results_dataset,
)
from Learning.thermflex_daily_results.schema import (
    CO2_ONLY_TARGET_COLUMNS,
    DISPATCH_COST_COMPONENT_TARGET_COLUMNS,
    DISPATCH_SOURCE_CO2_TARGET_COLUMNS,
    DISPATCH_SOURCE_GENERATION_TARGET_COLUMNS,
    HEAT_COST_ALLOCATED_CO2_ABSOLUTE_TARGET_COLUMNS,
    HEAT_COST_TOTAL_CO2_ABSOLUTE_TARGET_COLUMNS,
    ROBUST_KPI_ABSOLUTE_TARGET_COLUMNS,
    ROBUST_KPI_TARGET_COLUMNS,
    SHIFTED_REBOUND_ONLY_TARGET_COLUMNS,
    TABLE_09_PAPER_TARGET_COLUMNS,
    TARGET_COLUMNS,
)
from Learning.thermflex_daily_results.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


def train_daily_results_model(
    *,
    family_hash: str | None = None,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    group_column: str = "split_group_bundle",
    test_size: float = 0.34,
    random_state: int = 42,
    target_profile: str = "all",
) -> dict[str, Any]:
    """
    Train the first XGB baseline on the curated ThermFlex daily-results dataset.

    When `family_hash` is omitted, the preferred dataset should already have been
    exported and its hash passed in by the caller. This function assumes the
    curated dataset already exists under `Learning/datasets/`.
    """

    if family_hash is None:
        raise ValueError("[thermflex_daily_results] train_daily_results_model requires family_hash.")
    dataset_bundle = load_dataset(dataset_root, family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_daily_results] curated dataset not found under Learning/datasets for family_hash="
            f"{family_hash}"
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError(
            "[thermflex_daily_results] curated dataset is missing `truth_dataset.csv`."
        )
    truth_df = pd.read_csv(truth_csv_path)
    validate_truth_row_alignment(
        dataset_bundle,
        len(truth_df),
        context_label="[thermflex_daily_results] train_daily_results_model",
    )
    split = build_grouped_holdout_split(
        truth_df=truth_df,
        group_column=group_column,
        test_size=test_size,
        random_state=random_state,
    )
    x = np.asarray(dataset_bundle["X"], dtype=float)
    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    requested_target_names = _resolve_target_profile(target_profile)
    missing_requested = [target for target in requested_target_names if target not in all_target_names]
    if missing_requested:
        raise ValueError(
            "[thermflex_daily_results] requested target profile contains unknown targets: "
            + ", ".join(missing_requested)
        )
    available_target_names = [target for target in requested_target_names if not truth_df[target].isna().any()]
    excluded_target_names = [target for target in requested_target_names if target not in available_target_names]
    if not available_target_names:
        raise ValueError("[thermflex_daily_results] no fully available targets left for baseline training.")
    target_indices = [all_target_names.index(target) for target in available_target_names]
    y = np.asarray(dataset_bundle["Y"], dtype=float)[:, target_indices]
    x_train = x[split.train_index, :]
    x_test = x[split.test_index, :]
    y_train = y[split.train_index, :]
    y_test = y[split.test_index, :]
    target_names = list(available_target_names)
    target_transforms = {target: _resolve_target_transform(target) for target in target_names}
    if "feature_mode" not in dataset_bundle["meta"]:
        raise KeyError("[thermflex_daily_results] dataset metadata missing required `feature_mode`.")
    feature_mode = str(dataset_bundle["meta"]["feature_mode"])

    models: list[Any] = []
    for target_idx, _target_name in enumerate(target_names):
        transformed_train_target = _apply_target_transform(
            y_train[:, target_idx],
            target_transforms[_target_name],
        )
        model = XGBRegressor(**_resolve_model_params(_target_name, random_state=random_state))
        model.fit(x_train, transformed_train_target)
        models.append(model)

    y_pred = np.column_stack(
        [
            _invert_target_transform(
                model.predict(x_test),
                target_transforms[target_name],
            )
            for model, target_name in zip(models, target_names)
        ]
    )
    metrics_df = _metric_block(y_true=y_test, y_pred=y_pred, target_names=target_names)
    model_id = f"thermflex_daily_results_xgb_{target_profile}_{family_hash[:12]}"
    artifact_dir = Path(model_root).resolve() / model_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "thermflex_daily_results_xgb.joblib"
    meta_path = artifact_dir / "thermflex_daily_results_xgb.meta.json"
    metrics_csv_path = artifact_dir / "holdout_metrics.csv"
    split_json_path = artifact_dir / "holdout_split.json"
    dump(
        {
            "models": models,
            "target_names": target_names,
            "target_transforms": target_transforms,
            "feature_columns": list(dataset_bundle["meta"]["encoded_feature_columns"]),
            "feature_mode": feature_mode,
            "family_hash": family_hash,
        },
        artifact_path,
    )
    metrics_df.to_csv(metrics_csv_path, index=False)
    split_payload = {
        "group_column": group_column,
        "test_size": float(test_size),
        "random_state": int(random_state),
        "train_groups": split.train_groups,
        "test_groups": split.test_groups,
        "n_train_rows": int(len(split.train_index)),
        "n_test_rows": int(len(split.test_index)),
    }
    split_json_path.write_text(json.dumps(split_payload, indent=2), encoding="utf-8")
    meta = {
        "model_type": "xgb_targetwise",
        "family_hash": family_hash,
        "artifact_path": str(artifact_path),
        "metrics_csv_path": str(metrics_csv_path),
        "split_json_path": str(split_json_path),
        "target_names": target_names,
        "target_transforms": target_transforms,
        "target_profile": target_profile,
        "feature_mode": feature_mode,
        "group_column": group_column,
        "test_size": float(test_size),
        "random_state": int(random_state),
        "excluded_target_names": excluded_target_names,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_model(
        settings_stub,
        family_hash,
        model_id,
        {
            "source": "thermflex_daily_results_training",
            "backend_name": "xgb_targetwise",
            "artifact_path": str(artifact_path),
            "meta_path": str(meta_path),
            "is_active": True,
            "is_preferred": False,
            "validation_stage": "candidate",
            "signature_hash": family_hash,
        },
    )
    summary = {
        "family_hash": family_hash,
        "model_id": model_id,
        "group_column": group_column,
        "target_profile": target_profile,
        "n_train_rows": int(len(split.train_index)),
        "n_test_rows": int(len(split.test_index)),
        "train_groups": split.train_groups,
        "test_groups": split.test_groups,
        "mean_mae": float(metrics_df["mae"].mean()),
        "mean_rmse": float(metrics_df["rmse"].mean()),
        "mean_r2": float(metrics_df["r2"].dropna().mean()) if metrics_df["r2"].notna().any() else float("nan"),
        "excluded_target_names": excluded_target_names,
    }
    update_model_status(
        settings_stub,
        family_hash,
        model_id,
        validation_stage="candidate",
        is_active=True,
        is_preferred=False,
        extra_fields={"holdout_summary": summary},
    )
    return {
        "summary": summary,
        "artifact_dir": artifact_dir,
        "artifact_path": artifact_path,
        "metrics_csv_path": metrics_csv_path,
        "split_json_path": split_json_path,
    }


def export_and_train_xgb_baseline(
    *,
    source_roots: list[Path],
    feature_mode: str = "default",
    include_partial_bundles: bool = False,
    include_pilot_bundles: bool = False,
    include_checkpoint_bundles: bool = False,
    min_checkpoint_rows: int = 30,
    include_legacy_bundles: bool = True,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    target_profile: str = "all",
) -> dict[str, Any]:
    """Convenience entry point: export curated dataset, then train the first XGB baseline."""

    dataset_result = export_curated_daily_results_dataset(
        source_roots=source_roots,
        dataset_root=dataset_root,
        registry_path=registry_path,
        feature_mode=feature_mode,
        include_partial_bundles=include_partial_bundles,
        include_pilot_bundles=include_pilot_bundles,
        include_checkpoint_bundles=include_checkpoint_bundles,
        min_checkpoint_rows=min_checkpoint_rows,
        include_legacy_bundles=include_legacy_bundles,
    )
    model_result = train_daily_results_model(
        family_hash=dataset_result.family_hash,
        dataset_root=dataset_root,
        model_root=model_root,
        registry_path=registry_path,
        target_profile=target_profile,
    )
    return {
        "dataset_result": dataset_result,
        "model_result": model_result,
    }


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if len(values) <= 1 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))


def _resolve_target_profile(target_profile: str) -> list[str]:
    """Map a named training profile to an explicit ordered target list."""

    profile = str(target_profile).strip().lower()
    if profile == "all":
        return list(TARGET_COLUMNS)
    if profile == "robust_kpi":
        return list(ROBUST_KPI_TARGET_COLUMNS)
    if profile == "robust_kpi_absolute":
        return list(ROBUST_KPI_ABSOLUTE_TARGET_COLUMNS)
    if profile == "heat_cost_total_co2_absolute":
        return list(HEAT_COST_TOTAL_CO2_ABSOLUTE_TARGET_COLUMNS)
    if profile == "heat_cost_allocated_co2_absolute":
        return list(HEAT_COST_ALLOCATED_CO2_ABSOLUTE_TARGET_COLUMNS)
    if profile == "dispatch_source_co2":
        return list(DISPATCH_SOURCE_CO2_TARGET_COLUMNS)
    if profile == "dispatch_cost_components":
        return list(DISPATCH_COST_COMPONENT_TARGET_COLUMNS)
    if profile == "dispatch_source_generation":
        return list(DISPATCH_SOURCE_GENERATION_TARGET_COLUMNS)
    if profile == "table_09_paper":
        return list(TABLE_09_PAPER_TARGET_COLUMNS)
    if profile == "shifted_rebound_only":
        return list(SHIFTED_REBOUND_ONLY_TARGET_COLUMNS)
    if profile == "co2_only":
        return list(CO2_ONLY_TARGET_COLUMNS)
    raise ValueError(f"[thermflex_daily_results] unsupported target profile: {target_profile}")


def _resolve_target_transform(target_name: str) -> str:
    """Return the explicit transform used for one target during fitting."""

    if target_name in {
        "dispatch_operating_cost_pct_change",
        "dispatch_operating_cost_eur_delta",
        "dispatch_heat_operating_cost_eur_delta",
        "fuel_cost_eur_delta",
        "co2_cost_eur_delta",
        "variable_opex_eur_delta",
        "startup_cost_eur_delta",
    }:
        return "signed_log1p"
    if target_name in {
        "co2_emissions_total_t_delta",
        "district_gas_boiler_co2_t_delta",
        "district_gas_chp_co2_t_delta",
        "dispatch_heat_allocated_co2_t_delta",
        "district_gas_chp_thermal_generation_kwh_delta",
        "district_gas_chp_electric_generation_kwh_delta",
        "district_heat_pump_generation_kwh_delta",
        "district_external_heat_generation_kwh_delta",
        "district_waste_incineration_generation_kwh_delta",
    }:
        return "signed_log1p"
    return "identity"


def _resolve_model_params(target_name: str, *, random_state: int) -> dict[str, Any]:
    """Return one explicit XGB parameter set per daily target family."""

    base_params: dict[str, Any] = {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": random_state,
        "n_jobs": 1,
    }
    if target_name == "district_gas_boiler_generation_kwh_delta":
        return {
            **base_params,
            "n_estimators": 900,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 1.0,
            "colsample_bytree": 0.7,
            "min_child_weight": 5,
            "reg_lambda": 1.0,
        }
    if target_name == "district_gas_boiler_peak_kw_delta":
        return {
            **base_params,
            "n_estimators": 300,
            "max_depth": 2,
            "learning_rate": 0.03,
            "subsample": 1.0,
            "colsample_bytree": 0.85,
            "min_child_weight": 3,
            "reg_lambda": 1.0,
        }
    if target_name == "co2_emissions_total_pct_change":
        return {
            **base_params,
            "n_estimators": 900,
            "max_depth": 2,
            "learning_rate": 0.05,
            "subsample": 1.0,
            "colsample_bytree": 0.7,
            "min_child_weight": 3,
            "reg_lambda": 1.0,
        }
    if target_name in {
        "dispatch_heat_operating_cost_eur_delta",
        "fuel_cost_eur_delta",
        "co2_cost_eur_delta",
        "co2_emissions_total_t_delta",
        "dispatch_heat_allocated_co2_t_delta",
    }:
        return {
            **base_params,
            "n_estimators": 800,
            "max_depth": 3,
            "learning_rate": 0.04,
            "subsample": 0.9,
            "colsample_bytree": 0.75,
            "min_child_weight": 4,
            "reg_lambda": 1.2,
        }
    if target_name in {"district_gas_boiler_co2_t_delta", "district_gas_chp_co2_t_delta"}:
        return {
            **base_params,
            "n_estimators": 700,
            "max_depth": 3,
            "learning_rate": 0.04,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "reg_lambda": 1.0,
        }
    if target_name in {
        "district_gas_chp_thermal_generation_kwh_delta",
        "district_gas_chp_electric_generation_kwh_delta",
        "district_heat_pump_generation_kwh_delta",
        "district_external_heat_generation_kwh_delta",
        "district_waste_incineration_generation_kwh_delta",
        "variable_opex_eur_delta",
    }:
        return {
            **base_params,
            "n_estimators": 700,
            "max_depth": 3,
            "learning_rate": 0.04,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "reg_lambda": 1.0,
        }
    if target_name == "thermflex_shifted_space_heat_kwh":
        return {
            **base_params,
            "n_estimators": 1200,
            "max_depth": 3,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.7,
            "min_child_weight": 3,
            "reg_lambda": 1.0,
        }
    if target_name == "thermflex_rebound_kwh":
        return {
            **base_params,
            "n_estimators": 700,
            "max_depth": 4,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "min_child_weight": 5,
            "reg_lambda": 1.0,
        }
    return base_params


def _apply_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    """Transform one target vector before fitting while keeping the mapping explicit."""

    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.log1p(np.abs(arr))
    raise ValueError(f"[thermflex_daily_results] unsupported target transform: {transform_name}")


def _invert_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    """Map predictions back to the original target scale for metrics and reporting."""

    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.expm1(np.abs(arr))
    raise ValueError(f"[thermflex_daily_results] unsupported target transform: {transform_name}")


def _metric_block(*, y_true: np.ndarray, y_pred: np.ndarray, target_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for idx, target in enumerate(target_names):
        err = y_pred[:, idx] - y_true[:, idx]
        rows.append(
            {
                "target": target,
                "mae": float(np.mean(np.abs(err))),
                "rmse": float(np.sqrt(np.mean(err * err))),
                "bias": float(np.mean(err)),
                "r2": _safe_r2(y_true[:, idx], y_pred[:, idx]),
            }
        )
    return pd.DataFrame(rows)
