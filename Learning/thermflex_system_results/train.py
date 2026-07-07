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
from Learning.datasets.validate_alignment import validate_truth_dataset_alignment
from Learning.registry.register_model import register_model
from Learning.registry.update_model_status import update_model_status
from Learning.thermflex_system_results.dataset_builder import (
    _DEFAULT_DATASET_ROOT,
    _DEFAULT_REGISTRY_PATH,
    export_curated_system_results_dataset,
)
from Learning.thermflex_system_results.schema import (
    DISPATCH_KPI_CORE_TARGET_COLUMNS,
    DISPATCH_KPI_PAPER_TARGET_COLUMNS,
    ROBUST_HEAT_SYSTEM_TARGET_COLUMNS,
)
from Learning.thermflex_system_results.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


def train_system_results_model(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    group_column: str = "split_group_case",
    test_size: float = 0.25,
    random_state: int = 42,
    target_profile: str = "all",
) -> dict[str, Any]:
    """Train the first target-wise XGB baseline on the curated ThermFlex system dataset."""

    dataset_bundle = load_dataset(dataset_root, family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_system_results] curated dataset not found under Learning/datasets for family_hash="
            f"{family_hash}"
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_system_results] curated dataset is missing `truth_dataset.csv`.")
    truth_df = pd.read_csv(truth_csv_path)
    validate_truth_dataset_alignment(
        dataset_bundle=dataset_bundle,
        truth_df=truth_df,
        context_label="thermflex_system_results",
    )
    split = build_grouped_holdout_split(
        truth_df=truth_df,
        group_column=group_column,
        test_size=test_size,
        random_state=random_state,
    )
    x = np.asarray(dataset_bundle["X"], dtype=float)
    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    requested_target_names = _resolve_target_profile(
        target_profile,
        available_target_names=all_target_names,
    )
    missing_requested = [target for target in requested_target_names if target not in all_target_names]
    if missing_requested:
        raise ValueError(
            "[thermflex_system_results] requested target profile contains unknown targets: "
            + ", ".join(missing_requested)
        )
    target_indices = [all_target_names.index(target) for target in requested_target_names]
    y = np.asarray(dataset_bundle["Y"], dtype=float)[:, target_indices]
    target_names = list(requested_target_names)
    x_train = x[split.train_index, :]
    x_test = x[split.test_index, :]
    y_train = y[split.train_index, :]
    y_test = y[split.test_index, :]
    target_transforms = {target: _resolve_target_transform(target) for target in target_names}

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
    model_id = f"thermflex_system_results_xgb_{target_profile}_{family_hash[:12]}"
    artifact_dir = Path(model_root).resolve() / model_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "thermflex_system_results_xgb.joblib"
    meta_path = artifact_dir / "thermflex_system_results_xgb.meta.json"
    metrics_csv_path = artifact_dir / "holdout_metrics.csv"
    split_json_path = artifact_dir / "holdout_split.json"

    dump(
        {
            "models": models,
            "target_names": target_names,
            "target_transforms": target_transforms,
            "feature_columns": list(dataset_bundle["meta"]["encoded_feature_columns"]),
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
        "group_column": group_column,
        "test_size": float(test_size),
        "random_state": int(random_state),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_model(
        settings_stub,
        family_hash,
        model_id,
        {
            "source": "thermflex_system_results_training",
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
    include_smoke_runs: bool = False,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    target_profile: str = "all",
    allowed_dispatch_tags: tuple[str, ...] | None = None,
    dispatch_kpi_mode: str = "none",
) -> dict[str, Any]:
    """Convenience entry point: export the curated system dataset and train the first baseline."""

    dataset_result = export_curated_system_results_dataset(
        include_smoke_runs=include_smoke_runs,
        dataset_root=dataset_root,
        registry_path=registry_path,
        allowed_dispatch_tags=allowed_dispatch_tags,
        dispatch_kpi_mode=dispatch_kpi_mode,
    )
    model_result = train_system_results_model(
        family_hash=dataset_result.family_hash,
        dataset_root=dataset_root,
        model_root=model_root,
        registry_path=registry_path,
        target_profile=target_profile,
    )
    return {"dataset_result": dataset_result, "model_result": model_result}


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if len(values) <= 1 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))


def _resolve_target_profile(target_profile: str, *, available_target_names: list[str] | None = None) -> list[str]:
    """Map a named training profile to an explicit ordered target list."""

    profile = str(target_profile).strip().lower()
    if profile == "all":
        if available_target_names is None:
            raise ValueError(
                "[thermflex_system_results] profile 'all' requires the concrete dataset target columns."
            )
        return list(available_target_names)
    if profile == "robust_heat_system":
        return list(ROBUST_HEAT_SYSTEM_TARGET_COLUMNS)
    if profile == "dispatch_kpi_core":
        return list(DISPATCH_KPI_CORE_TARGET_COLUMNS)
    if profile == "dispatch_kpi_paper":
        return list(DISPATCH_KPI_PAPER_TARGET_COLUMNS)
    raise ValueError(f"[thermflex_system_results] unsupported target profile: {target_profile}")


def _resolve_target_transform(target_name: str) -> str:
    """Return the explicit transform used for one target during fitting."""

    if target_name in {
        "dispatch_cost_eur",
        "dispatch_operating_cost_eur",
        "dispatch_heat_operating_cost_eur",
        "dispatch_objective_eur",
        "dispatch_penalty_total_eur",
        "grid_import_cost_eur",
        "grid_export_revenue_eur",
        "gas_chp_electric_value_eur",
        "fuel_cost_eur",
        "co2_cost_eur",
        "variable_opex_eur",
        "startup_cost_eur",
        "unserved_penalty_eur",
        "temperature_violation_penalty_eur",
        "thermflex_activation_penalty_eur",
        "spill_penalty_eur",
        "co2_emissions_total_t",
        "district_gas_boiler_co2_t",
        "district_gas_chp_co2_t",
    }:
        return "log1p"
    return "identity"


def _resolve_model_params(target_name: str, *, random_state: int) -> dict[str, Any]:
    """
    Return one explicit XGB parameter set per target family.

    Most system targets are trained with one conservative shared baseline. The
    system cost target stayed the weakest KPI after feature improvements, so it
    gets its own documented parameter set derived from a grouped-holdout sweep
    on the current `thermflex_system_results_v1` dataset family.
    """

    base_params: dict[str, Any] = {
        "n_estimators": 250,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": random_state,
        "n_jobs": 1,
    }
    if target_name == "dispatch_cost_eur":
        return {
            **base_params,
            "n_estimators": 300,
            "max_depth": 4,
            "learning_rate": 0.08,
            "subsample": 1.0,
            "colsample_bytree": 1.0,
            "min_child_weight": 1,
            "reg_lambda": 1.0,
        }
    if target_name == "co2_emissions_total_t":
        return {
            **base_params,
            "n_estimators": 150,
            "max_depth": 6,
            "learning_rate": 0.03,
            "subsample": 1.0,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "reg_lambda": 3.0,
        }
    if target_name in {
        "E_district_gas_chp_electric_generation_kWh",
        "E_district_gas_chp_thermal_generation_kWh",
        "E_district_gas_chp_fuel_input_kWh",
    }:
        return {
            **base_params,
            "n_estimators": 600,
            "max_depth": 3,
            "learning_rate": 0.08,
            "subsample": 0.8,
            "colsample_bytree": 1.0,
            "min_child_weight": 3,
            "reg_lambda": 3.0,
        }
    if target_name == "E_district_thermal_storage_charge_kWh":
        return {
            **base_params,
            "n_estimators": 150,
            "max_depth": 6,
            "learning_rate": 0.03,
            "subsample": 1.0,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "reg_lambda": 3.0,
        }
    if target_name == "E_district_thermal_storage_discharge_kWh":
        return {
            **base_params,
            "n_estimators": 150,
            "max_depth": 3,
            "learning_rate": 0.08,
            "subsample": 1.0,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "reg_lambda": 3.0,
        }
    if target_name == "thermflex_rebound_kwh":
        return {
            **base_params,
            "n_estimators": 400,
            "max_depth": 2,
            "learning_rate": 0.05,
            "subsample": 1.0,
            "colsample_bytree": 1.0,
            "min_child_weight": 1,
            "reg_lambda": 1.0,
        }
    return base_params


def _apply_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    """Transform one target vector before fitting while keeping the mapping explicit."""

    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "log1p":
        return np.log1p(arr)
    raise ValueError(f"[thermflex_system_results] unsupported target transform: {transform_name}")


def _invert_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    """Map predictions back to the original target scale for metrics and reporting."""

    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "log1p":
        return np.expm1(arr)
    raise ValueError(f"[thermflex_system_results] unsupported target transform: {transform_name}")


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
