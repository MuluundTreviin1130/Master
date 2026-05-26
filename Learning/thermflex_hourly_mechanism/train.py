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
from Learning.registry.register_model import register_model
from Learning.registry.update_model_status import update_model_status
from Learning.thermflex_hourly_mechanism.dataset_builder import (
    _DEFAULT_DATASET_ROOT,
    _DEFAULT_REGISTRY_PATH,
    export_curated_hourly_mechanism_dataset,
)
from Learning.thermflex_hourly_mechanism.schema import MECHANISM_CORE_EVENT_TARGET_COLUMNS
from Learning.thermflex_hourly_mechanism.schema import MECHANISM_CORE_TARGET_COLUMNS
from Learning.thermflex_hourly_mechanism.schema import MECHANISM_ENERGY_INTENSIVE_TARGET_COLUMNS
from Learning.thermflex_hourly_mechanism.schema import MECHANISM_ENERGY_STATE_INTENSIVE_TARGET_COLUMNS
from Learning.thermflex_hourly_mechanism.schema import MECHANISM_ENERGY_TARGET_COLUMNS
from Learning.thermflex_hourly_mechanism.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


def train_hourly_mechanism_model(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    group_column: str = "split_group_run",
    test_size: float = 0.25,
    random_state: int = 42,
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    target_profile: str = "mechanism_core",
    feature_preset: str = "all",
    target_transform_profile: str = "default",
) -> dict[str, Any]:
    dataset_bundle = load_dataset(dataset_root, family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] curated dataset not found under Learning/datasets for family_hash="
            f"{family_hash}"
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_hourly_mechanism] curated dataset is missing `truth_dataset.csv`.")
    truth_df = pd.read_csv(truth_csv_path)
    split = build_grouped_holdout_split(
        truth_df=truth_df,
        group_column=group_column,
        test_size=test_size,
        random_state=random_state,
        split_strategy=split_strategy,
        stratify_column=stratify_column,
    )
    all_feature_names = [str(value) for value in dataset_bundle["meta"]["encoded_feature_columns"]]
    selected_feature_names = _resolve_feature_preset(all_feature_names, feature_preset)
    selected_feature_indices = [all_feature_names.index(name) for name in selected_feature_names]
    x = np.asarray(dataset_bundle["X"], dtype=float)[:, selected_feature_indices]
    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    target_names = list(_resolve_target_profile(target_profile))
    target_indices = [all_target_names.index(target) for target in target_names]
    y = np.asarray(dataset_bundle["Y"], dtype=float)[:, target_indices]
    x_train = x[split.train_index, :]
    x_test = x[split.test_index, :]
    y_train = y[split.train_index, :]
    y_test = y[split.test_index, :]
    target_transforms = {
        target: _resolve_target_transform(target, profile=target_transform_profile)
        for target in target_names
    }

    models: list[Any] = []
    for target_idx, target_name in enumerate(target_names):
        transformed_train_target = _apply_target_transform(y_train[:, target_idx], target_transforms[target_name])
        model = XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
        model.fit(x_train, transformed_train_target)
        models.append(model)

    y_pred = np.column_stack(
        [
            _invert_target_transform(model.predict(x_test), target_transforms[target_name])
            for model, target_name in zip(models, target_names)
        ]
    )
    metrics_df = _metric_block(y_true=y_test, y_pred=y_pred, target_names=target_names)
    model_id = f"thermflex_hourly_mechanism_xgb_{target_profile}_{family_hash[:12]}"
    if str(feature_preset) != "all":
        model_id = f"{model_id}_features_{_slug(feature_preset)}"
    if str(target_transform_profile) != "default":
        model_id = f"{model_id}_transforms_{_slug(target_transform_profile)}"
    if str(split.split_strategy) != "group_shuffle" or split.stratify_column is not None:
        split_suffix = _slug(split.split_strategy)
        if split.stratify_column is not None:
            split_suffix = f"{split_suffix}_{_slug(split.stratify_column)}"
        model_id = f"{model_id}_split_{split_suffix}"
    artifact_dir = Path(model_root).resolve() / model_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "thermflex_hourly_mechanism_xgb.joblib"
    meta_path = artifact_dir / "thermflex_hourly_mechanism_xgb.meta.json"
    metrics_csv_path = artifact_dir / "holdout_metrics.csv"
    split_json_path = artifact_dir / "holdout_split.json"

    dump(
        {
            "models": models,
            "target_names": target_names,
            "target_transforms": target_transforms,
            "feature_columns": list(selected_feature_names),
            "feature_mode": str(dataset_bundle["meta"].get("feature_mode", "full")),
            "feature_preset": str(feature_preset),
            "family_hash": family_hash,
        },
        artifact_path,
    )
    metrics_df.to_csv(metrics_csv_path, index=False)
    split_json_path.write_text(
        json.dumps(
            {
                "group_column": group_column,
                "test_size": float(test_size),
                "random_state": int(random_state),
                "split_strategy": split.split_strategy,
                "stratify_column": split.stratify_column,
                "train_groups": split.train_groups,
                "test_groups": split.test_groups,
                "n_train_rows": int(len(split.train_index)),
                "n_test_rows": int(len(split.test_index)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    meta = {
        "model_type": "xgb_targetwise",
        "family_hash": family_hash,
        "artifact_path": str(artifact_path),
        "metrics_csv_path": str(metrics_csv_path),
        "split_json_path": str(split_json_path),
        "target_names": target_names,
        "target_transforms": target_transforms,
        "target_profile": target_profile,
        "feature_preset": str(feature_preset),
        "target_transform_profile": str(target_transform_profile),
        "feature_mode": str(dataset_bundle["meta"].get("feature_mode", "full")),
        "group_column": group_column,
        "test_size": float(test_size),
        "random_state": int(random_state),
        "split_strategy": split.split_strategy,
        "stratify_column": split.stratify_column,
        "n_features": int(len(selected_feature_names)),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_model(
        settings_stub,
        family_hash,
        model_id,
        {
            "source": "thermflex_hourly_mechanism_training",
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
        "split_strategy": split.split_strategy,
        "stratify_column": split.stratify_column,
        "target_profile": target_profile,
        "feature_preset": str(feature_preset),
        "target_transform_profile": str(target_transform_profile),
        "n_train_rows": int(len(split.train_index)),
        "n_test_rows": int(len(split.test_index)),
        "n_features": int(len(selected_feature_names)),
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
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    target_profile: str = "mechanism_core",
    family_slice: str = "all",
    feature_mode: str = "full",
) -> dict[str, Any]:
    dataset_result = export_curated_hourly_mechanism_dataset(
        dataset_root=dataset_root,
        registry_path=registry_path,
        target_profile=target_profile,
        family_slice=family_slice,
        feature_mode=feature_mode,
    )
    model_result = train_hourly_mechanism_model(
        family_hash=dataset_result.family_hash,
        dataset_root=dataset_root,
        model_root=model_root,
        registry_path=registry_path,
        target_profile=target_profile,
    )
    return {"dataset_result": dataset_result, "model_result": model_result}


def _resolve_target_profile(target_profile: str) -> tuple[str, ...]:
    profile = str(target_profile).strip().lower()
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


def _resolve_feature_preset(feature_names: list[str], feature_preset: str) -> list[str]:
    """Select one explicit encoded-feature contract for mechanism training."""

    preset = str(feature_preset).strip().lower()
    if preset == "all":
        return list(feature_names)
    if preset == "no_case_label":
        selected = [name for name in feature_names if not name.startswith("case_label_")]
    elif preset == "no_case_or_cohort_label":
        selected = [
            name
            for name in feature_names
            if not name.startswith("case_label_") and not name.startswith("cohort_key_")
        ]
    else:
        raise ValueError(f"[thermflex_hourly_mechanism] unsupported feature preset: {feature_preset}")
    if not selected:
        raise ValueError(f"[thermflex_hourly_mechanism] feature preset selected no columns: {feature_preset}")
    return selected


def _resolve_target_transform(target_name: str, *, profile: str = "default") -> str:
    transform_profile = str(profile).strip().lower()
    if transform_profile == "mechanism_mass_identity":
        return "identity"
    if transform_profile == "positive_components_identity":
        if target_name in {
            "cohort_preheat_extra_kwh",
            "cohort_cutback_shed_kwh",
            "cohort_preheat_extra_wh_per_m2",
            "cohort_cutback_shed_wh_per_m2",
        }:
            return "identity"
        if target_name == "cohort_temperature_violation_degree_h":
            return "identity"
    elif transform_profile != "default":
        raise ValueError(
            "[thermflex_hourly_mechanism] unsupported target transform profile: "
            f"{profile}"
        )
    if target_name in {
        "cohort_q_delta_kwh",
        "cohort_preheat_extra_kwh",
        "cohort_cutback_shed_kwh",
        "cohort_q_delta_wh_per_m2",
        "cohort_preheat_extra_wh_per_m2",
        "cohort_cutback_shed_wh_per_m2",
    }:
        return "signed_log1p"
    return "identity"


def _slug(value: str) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _resolve_model_params(target_name: str, *, random_state: int) -> dict[str, Any]:
    base_params: dict[str, Any] = {
        "n_estimators": 350,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": random_state,
        "n_jobs": 1,
    }
    if target_name == "cohort_t_in_weighted_mean_c":
        return {**base_params, "n_estimators": 250, "max_depth": 4, "learning_rate": 0.03}
    if target_name in {"cohort_event_start_count", "cohort_flex_active_member_share"}:
        return {**base_params, "n_estimators": 250, "max_depth": 3, "learning_rate": 0.04}
    if target_name == "cohort_temperature_violation_degree_h":
        return {**base_params, "n_estimators": 200, "max_depth": 3, "learning_rate": 0.05}
    return base_params


def _apply_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.log1p(np.abs(arr))
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported target transform: {transform_name}")


def _invert_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.expm1(np.abs(arr))
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported target transform: {transform_name}")


def _metric_block(*, y_true: np.ndarray, y_pred: np.ndarray, target_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for idx, target_name in enumerate(target_names):
        true = np.asarray(y_true[:, idx], dtype=float)
        pred = np.asarray(y_pred[:, idx], dtype=float)
        mae = float(np.mean(np.abs(pred - true)))
        rmse = float(np.sqrt(np.mean(np.square(pred - true))))
        bias = float(np.mean(pred - true))
        rows.append(
            {
                "target": target_name,
                "mae": mae,
                "rmse": rmse,
                "bias": bias,
                "r2": _safe_r2(true, pred),
            }
        )
    return pd.DataFrame(rows)


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if len(values) <= 1 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))
