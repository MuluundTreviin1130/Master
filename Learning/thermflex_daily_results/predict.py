from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import load

from Learning.thermflex_daily_results.features import add_engineered_feature_columns
from Learning.thermflex_daily_results.dataset_builder import (
    _enrich_with_canonical_daily_context,
    _load_policy_metadata,
    _normalize_feature_mode,
    _resolved_numeric_feature_columns,
)
from Learning.thermflex_daily_results.schema import (
    CATEGORICAL_FEATURE_COLUMNS,
    CONTEXT_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
)


@dataclass(frozen=True)
class SurrogateDailyPredictionResult:
    prediction_frame: pd.DataFrame
    model_id: str
    target_names: tuple[str, ...]
    template_screen_csv: Path


_TEMPLATE_REQUIRED_COLUMNS: tuple[str, ...] = (
    "date",
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "dh_space_heat_total_kwh",
    "dh_total_kwh",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "mc_auction_mean_eur_mwh",
    "gas_price_mean_eur_mwh_fuel",
    "co2_price_mean_eur_tco2",
    "dispatch_operating_cost_eur_ref",
    "co2_emissions_total_t_ref",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_generation_kwh_ref",
)


def predict_daily_results(
    *,
    template_screen_csv: Path | str,
    model_dir: Path | str,
    flex_override_name: str,
    flex_case_label: str | None = None,
    allow_unseen_policy_categories: bool = False,
) -> SurrogateDailyPredictionResult:
    """
    Predict one surrogate daily screen from a heating-season template screen.

    The template contributes only the day context and reference-day columns.
    The target ThermFlex policy is taken explicitly from the supplied override.
    """

    template_path = Path(template_screen_csv).resolve()
    model_path = Path(model_dir).resolve()
    if not template_path.exists():
        raise FileNotFoundError(f"[thermflex_daily_results] template screen not found: {template_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"[thermflex_daily_results] model dir not found: {model_path}")

    model_bundle = load(model_path / "thermflex_daily_results_xgb.joblib")
    meta = json.loads((model_path / "thermflex_daily_results_xgb.meta.json").read_text(encoding="utf-8"))
    feature_mode = _resolve_model_feature_mode(model_bundle=model_bundle, meta=meta)
    template = _load_template_screen(template_path, feature_mode=feature_mode)
    policy_meta = _load_policy_metadata(override_name=flex_override_name)
    policy_label = (
        str(flex_case_label).strip()
        if flex_case_label is not None and str(flex_case_label).strip()
        else str(policy_meta["policy_case_label_canonical"]).strip()
    )
    if not policy_label:
        raise ValueError("[thermflex_daily_results] predicted screen requires a non-empty case label.")

    feature_frame = _build_feature_frame(
        template=template,
        policy_meta=policy_meta,
        policy_label=policy_label,
        feature_mode=feature_mode,
    )
    x_aligned = _encode_and_align_features(
        feature_frame=feature_frame,
        expected_feature_columns=list(model_bundle["feature_columns"]),
        feature_mode=feature_mode,
        allow_unseen_policy_categories=bool(allow_unseen_policy_categories),
    )
    predictions = _predict_target_block(
        model_bundle=model_bundle,
        x_aligned=x_aligned,
    )
    prediction_frame = _assemble_prediction_frame(
        template=template,
        predictions=predictions,
        flex_override_name=flex_override_name,
        flex_case_label=policy_label,
    )
    return SurrogateDailyPredictionResult(
        prediction_frame=prediction_frame,
        model_id=str(meta.get("family_hash", "")),
        target_names=tuple(str(name) for name in model_bundle["target_names"]),
        template_screen_csv=template_path,
    )


def _load_template_screen(path: Path, *, feature_mode: str) -> pd.DataFrame:
    """Load only the explicit context + REF contract needed for surrogate day inference."""

    frame = pd.read_csv(path)
    required_columns = _template_required_columns(feature_mode=feature_mode)
    missing = sorted(set(required_columns).difference(frame.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] template screen missing required columns: " + ", ".join(missing)
        )
    # Newer daily-surrogate feature contracts use canonical weather, load-shape
    # and cohort-composition context that older compact screen CSVs did not
    # export. The enrichment is date-keyed against the same Vienna 2023 SSOT
    # used during dataset construction, so missing columns remain explicit data
    # joins instead of runtime defaults.
    enriched = _enrich_with_canonical_daily_context(frame)
    output_columns = list(
        dict.fromkeys(
            [
                *required_columns,
                *CONTEXT_FEATURE_COLUMNS,
            ]
        )
    )
    present_output_columns = [column for column in output_columns if column in enriched.columns]
    out = enriched.loc[:, present_output_columns].copy()
    out["date"] = pd.to_datetime(out["date"], errors="raise")
    for column in [col for col in out.columns if col != "date"]:
        out[column] = pd.to_numeric(out[column], errors="raise")
    return out.sort_values("date").reset_index(drop=True)


def _build_feature_frame(
    *,
    template: pd.DataFrame,
    policy_meta: dict[str, Any],
    policy_label: str,
    feature_mode: str,
) -> pd.DataFrame:
    """Recreate the exact raw feature contract used by the curated daily dataset."""

    frame = template.copy()
    frame["day_of_year"] = frame["date"].dt.dayofyear.astype(int)
    frame["month"] = frame["date"].dt.month.astype(int)
    frame["day_of_week"] = frame["date"].dt.dayofweek.astype(int)
    frame["policy_case_label_canonical"] = policy_label
    frame["source_schema_version"] = "screen_v2_current"
    frame["policy_duration_h"] = float(policy_meta["policy_duration_h"])
    frame["policy_lower_relaxation_k"] = float(policy_meta["policy_lower_relaxation_k"])
    frame["policy_tau_h"] = float(policy_meta["policy_tau_h"])
    frame["policy_dispatch_horizon_h"] = float(policy_meta["policy_dispatch_horizon_h"])
    frame["policy_dispatch_rolling_commit_h"] = float(policy_meta["policy_dispatch_rolling_commit_h"])
    frame["policy_dispatch_lookahead_h"] = float(policy_meta["policy_dispatch_lookahead_h"])
    frame["policy_dispatch_is_rolling"] = float(policy_meta["policy_dispatch_is_rolling"])
    frame["policy_max_events_per_day"] = float(policy_meta["policy_max_events_per_day"])
    frame["policy_constant_lower_bound_c"] = float(policy_meta["policy_constant_lower_bound_c"])
    frame["policy_upper_only"] = float(bool(policy_meta["policy_upper_only"]))
    frame["policy_case_label_matches_export"] = float(
        str(policy_label).strip() == str(policy_meta["policy_case_label_canonical"]).strip()
    )
    feature_mode_normalized = _normalize_feature_mode(feature_mode)
    frame = add_engineered_feature_columns(
        frame,
        include_dispatch_economics=feature_mode_normalized
        in {"dispatch_economics", "dispatch_economics_stateful"},
        include_dispatch_state=feature_mode_normalized == "dispatch_economics_stateful",
    )
    numeric_feature_columns = list(_resolved_numeric_feature_columns(feature_mode=feature_mode_normalized))
    missing_numeric = sorted(set(numeric_feature_columns).difference(frame.columns))
    if missing_numeric:
        raise KeyError(
            "[thermflex_daily_results] feature frame missing required numeric columns: "
            + ", ".join(missing_numeric)
        )
    return frame


def _encode_and_align_features(
    *,
    feature_frame: pd.DataFrame,
    expected_feature_columns: list[str],
    feature_mode: str,
    allow_unseen_policy_categories: bool = False,
) -> np.ndarray:
    """One-hot encode the raw inference frame and align it to the trained model contract."""

    numeric_feature_columns = list(_resolved_numeric_feature_columns(feature_mode=feature_mode))
    raw = feature_frame.loc[:, numeric_feature_columns + list(CATEGORICAL_FEATURE_COLUMNS)].copy()
    encoded = pd.get_dummies(
        raw,
        columns=list(CATEGORICAL_FEATURE_COLUMNS),
        dtype=float,
    )
    encoded["date"] = pd.to_datetime(feature_frame["date"], errors="raise").map(pd.Timestamp.toordinal)
    encoded = encoded.apply(pd.to_numeric, errors="raise")

    expected_set = set(expected_feature_columns)
    category_prefixes = ("policy_case_label_canonical_", "source_schema_version_")
    unexpected = sorted(
        column
        for column in set(encoded.columns).difference(expected_set)
        if column.startswith(category_prefixes)
    )
    if allow_unseen_policy_categories:
        # This opt-in path is used for explicit draft extrapolation tables when
        # the numeric policy descriptors are in-contract but the exact case
        # label was absent during fitting. Other unexpected categorical schema
        # changes still fail.
        unexpected = [
            column
            for column in unexpected
            if not column.startswith("policy_case_label_canonical_")
        ]
    if unexpected:
        raise ValueError(
            "[thermflex_daily_results] inference frame produced unseen encoded columns: "
            + ", ".join(unexpected)
        )

    for feature_name in expected_feature_columns:
        if feature_name not in encoded.columns:
            if feature_name.startswith("policy_case_label_canonical_") or feature_name.startswith(
                "source_schema_version_"
            ):
                encoded[feature_name] = 0.0
                continue
            raise KeyError(
                "[thermflex_daily_results] inference frame missing encoded feature column: "
                f"{feature_name}"
            )
    encoded = encoded.loc[:, expected_feature_columns]
    return encoded.to_numpy(dtype=float)


def _template_required_columns(*, feature_mode: str) -> tuple[str, ...]:
    """Return the REF columns needed to rebuild the trained feature contract."""

    feature_mode_normalized = _normalize_feature_mode(feature_mode)
    columns = [*_TEMPLATE_REQUIRED_COLUMNS]
    if feature_mode_normalized in {"dispatch_economics", "dispatch_economics_stateful"}:
        columns.extend(DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS)
    if feature_mode_normalized == "dispatch_economics_stateful":
        columns.extend(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS)
    return tuple(dict.fromkeys(columns))


def _resolve_model_feature_mode(*, model_bundle: dict[str, Any], meta: dict[str, Any]) -> str:
    """
    Resolve the trained daily feature mode from the model contract.

    New artifacts store `feature_mode` explicitly. For older artifacts created
    before that field existed, the encoded feature list is still authoritative:
    dispatch-only columns cannot appear in a default contract, so inference can
    derive the mode without padding or dropping any trained feature.
    """

    explicit = model_bundle.get("feature_mode", meta.get("feature_mode"))
    if explicit is not None:
        return _normalize_feature_mode(str(explicit))

    feature_columns = {str(column) for column in model_bundle["feature_columns"]}
    state_markers = set(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS).union(
        DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS
    )
    if feature_columns.intersection(state_markers):
        return "dispatch_economics_stateful"

    economics_markers = set(DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS).union(
        DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS
    )
    if feature_columns.intersection(economics_markers):
        return "dispatch_economics"
    return "default"


def _predict_target_block(*, model_bundle: dict[str, Any], x_aligned: np.ndarray) -> dict[str, np.ndarray]:
    """Run target-wise inference and map predictions back to original units."""

    target_names = [str(name) for name in model_bundle["target_names"]]
    target_transforms = {str(key): str(value) for key, value in model_bundle["target_transforms"].items()}
    predictions: dict[str, np.ndarray] = {}
    for model, target_name in zip(model_bundle["models"], target_names):
        raw = np.asarray(model.predict(x_aligned), dtype=float)
        predictions[target_name] = _invert_target_transform(raw, target_transforms[target_name])
    return predictions


def _assemble_prediction_frame(
    *,
    template: pd.DataFrame,
    predictions: dict[str, np.ndarray],
    flex_override_name: str,
    flex_case_label: str,
) -> pd.DataFrame:
    """Reconstruct a `heating_season_day_screen.csv`-style frame for Table 09."""

    required_targets = {
        "dispatch_operating_cost_pct_change",
        "co2_emissions_total_pct_change",
        "district_gas_boiler_peak_kw_delta",
        "district_gas_boiler_generation_kwh_delta",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
    }
    missing = sorted(required_targets.difference(predictions.keys()))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] selected model cannot reconstruct Table 09 screen; "
            "missing targets: "
            + ", ".join(missing)
        )

    out = template.copy()
    out["flex_case_label"] = flex_case_label
    out["flex_override_name"] = str(flex_override_name).strip()

    out["dispatch_operating_cost_pct_change"] = predictions["dispatch_operating_cost_pct_change"]
    out["dispatch_operating_cost_eur_flex"] = out["dispatch_operating_cost_eur_ref"] * (
        1.0 + out["dispatch_operating_cost_pct_change"] / 100.0
    )
    out["dispatch_operating_cost_eur_delta"] = (
        out["dispatch_operating_cost_eur_flex"] - out["dispatch_operating_cost_eur_ref"]
    )

    out["co2_emissions_total_pct_change"] = predictions["co2_emissions_total_pct_change"]
    out["co2_emissions_total_t_flex"] = out["co2_emissions_total_t_ref"] * (
        1.0 + out["co2_emissions_total_pct_change"] / 100.0
    )
    out["co2_emissions_total_t_delta"] = out["co2_emissions_total_t_flex"] - out["co2_emissions_total_t_ref"]

    out["district_gas_boiler_peak_kw_delta"] = predictions["district_gas_boiler_peak_kw_delta"]
    out["district_gas_boiler_peak_kw_flex"] = (
        out["district_gas_boiler_peak_kw_ref"] + out["district_gas_boiler_peak_kw_delta"]
    )
    out["district_gas_boiler_peak_pct_change"] = np.where(
        np.abs(out["district_gas_boiler_peak_kw_ref"].to_numpy(dtype=float)) > 1e-12,
        100.0 * out["district_gas_boiler_peak_kw_delta"] / out["district_gas_boiler_peak_kw_ref"],
        np.nan,
    )

    out["district_gas_boiler_generation_kwh_delta"] = predictions["district_gas_boiler_generation_kwh_delta"]
    out["district_gas_boiler_generation_kwh_flex"] = (
        out["district_gas_boiler_generation_kwh_ref"] + out["district_gas_boiler_generation_kwh_delta"]
    )
    out["district_gas_boiler_generation_pct_change"] = np.where(
        np.abs(out["district_gas_boiler_generation_kwh_ref"].to_numpy(dtype=float)) > 1e-12,
        100.0 * out["district_gas_boiler_generation_kwh_delta"] / out["district_gas_boiler_generation_kwh_ref"],
        np.nan,
    )

    out["thermflex_shifted_space_heat_kwh"] = np.clip(
        predictions["thermflex_shifted_space_heat_kwh"], 0.0, None
    )
    out["thermflex_rebound_kwh"] = np.clip(predictions["thermflex_rebound_kwh"], 0.0, None)
    out["thermflex_rebound_over_shifted_pct"] = np.where(
        np.abs(out["thermflex_shifted_space_heat_kwh"].to_numpy(dtype=float)) > 1e-12,
        100.0 * out["thermflex_rebound_kwh"] / out["thermflex_shifted_space_heat_kwh"],
        np.nan,
    )

    return out


def _invert_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    """Map predictions back to the original target scale for reporting/inference."""

    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.expm1(np.abs(arr))
    raise ValueError(f"[thermflex_daily_results] unsupported target transform for inference: {transform_name}")
