from __future__ import annotations

"""Build explicit Upper-only trigger-state labels from hourly mechanism truth.

The daily `rebound_kwh` metric is a derived outcome.  For Upper-only cases the
current failure mode is more specific: the surrogate often predicts an active
rebound-like positive tail on days where the true sequence has shifted energy
but no meaningful rebound.  This exporter persists the intermediate state
contract so the next router can learn trigger state directly:

- whether a meaningful negative/cutback hour exists,
- where the first cutback occurs,
- how much positive mass follows that cutback,
- whether the day is shifted-without-rebound,
- how the current model sequence differs from truth.

It is diagnostic only.  It writes artifacts under the selected model's
`diagnostics/` folder and does not register or promote a model.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_subcontracts import (
    _load_all_predictions,
    _safe_r2,
    predicted_or_true_metric,
)
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context
from Optimization.run.analysis.select_vienna_dh_thermflex_representative_days import _build_daily_features


@dataclass(frozen=True)
class TriggerStateLabelResult:
    output_dir: Path
    daily_csv: Path
    hourly_csv: Path
    summary_json: Path


def build_upper_only_trigger_state_labels(
    *,
    model_dir: Path,
    dataset_dir: Path,
    output_dir: Path | None = None,
    rebound_activation_threshold_kwh: float = 250_000.0,
    shifted_threshold_kwh: float = 1_000_000.0,
    hourly_deadband_kwh: float = 1_000.0,
) -> TriggerStateLabelResult:
    """Persist daily and hourly trigger-state labels for one model/dataset pair."""

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    output_root = (
        Path(output_dir).resolve()
        if output_dir is not None
        else model_root / "diagnostics" / "upper_only_trigger_state_labels"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    frame, split_payload = _load_all_predictions(model_dir=model_root, dataset_dir=dataset_root)
    _validate_inputs(
        frame=frame,
        rebound_activation_threshold_kwh=rebound_activation_threshold_kwh,
        shifted_threshold_kwh=shifted_threshold_kwh,
        hourly_deadband_kwh=hourly_deadband_kwh,
    )
    test_groups = {str(value) for value in split_payload["test_groups"]}
    frame = frame.copy()
    frame["is_test"] = frame["split_group_run"].astype(str).isin(test_groups)

    daily_df, hourly_df = _build_label_frames(
        frame=frame,
        rebound_activation_threshold_kwh=float(rebound_activation_threshold_kwh),
        shifted_threshold_kwh=float(shifted_threshold_kwh),
        hourly_deadband_kwh=float(hourly_deadband_kwh),
    )

    daily_csv = output_root / "daily_trigger_state_labels.csv"
    hourly_csv = output_root / "hourly_trigger_state_labels.csv"
    summary_json = output_root / "trigger_state_label_summary.json"
    daily_df.to_csv(daily_csv, index=False)
    hourly_df.to_csv(hourly_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "rebound_activation_threshold_kwh": float(rebound_activation_threshold_kwh),
        "shifted_threshold_kwh": float(shifted_threshold_kwh),
        "hourly_deadband_kwh": float(hourly_deadband_kwh),
        "n_days": int(len(daily_df)),
        "n_test_days": int(daily_df["is_test"].astype(bool).sum()),
        "n_hourly_rows": int(len(hourly_df)),
        "daily_csv": str(daily_csv),
        "hourly_csv": str(hourly_csv),
        "label_counts": _label_counts(daily_df),
        "prediction_quality": _prediction_quality(daily_df),
        "worst_test_days": _worst_test_days(daily_df),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return TriggerStateLabelResult(
        output_dir=output_root,
        daily_csv=daily_csv,
        hourly_csv=hourly_csv,
        summary_json=summary_json,
    )


def _build_label_frames(
    *,
    frame: pd.DataFrame,
    rebound_activation_threshold_kwh: float,
    shifted_threshold_kwh: float,
    hourly_deadband_kwh: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build one daily label row and 24 hourly state rows per run/day."""

    daily_rows: list[dict[str, Any]] = []
    hourly_rows: list[pd.DataFrame] = []
    for (run_dir, day), group in frame.groupby(["run_dir", "day"], sort=True):
        ordered = group.sort_values(["timestamp", "cohort_key"]).copy()
        q_ref = ordered.groupby("timestamp", sort=True)["cohort_q_heat_ref_kwh"].sum()
        q_true = ordered.groupby("timestamp", sort=True)["cohort_q_heat_kwh"].sum()
        q_pred_delta = ordered.groupby("timestamp", sort=True)["q_delta_pred_kwh"].sum()
        q_pred = q_ref + q_pred_delta

        true_delta = q_true.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        pred_delta = q_pred.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        true_state = _sequence_state(true_delta, hourly_deadband_kwh=hourly_deadband_kwh)
        pred_state = _sequence_state(pred_delta, hourly_deadband_kwh=hourly_deadband_kwh)
        true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
        pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref)

        shifted_true = predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh")
        rebound_true = predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh")
        peak_true = predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw")
        shifted_pred = predicted_or_true_metric(pred_metrics, "thermflex_shifted_space_heat_kwh")
        rebound_pred = predicted_or_true_metric(pred_metrics, "thermflex_rebound_kwh")
        peak_pred = predicted_or_true_metric(pred_metrics, "thermflex_peak_change_kw")

        true_rebound_active = rebound_true >= rebound_activation_threshold_kwh
        pred_rebound_active = rebound_pred >= rebound_activation_threshold_kwh
        true_shifted_without_rebound = (
            shifted_true >= shifted_threshold_kwh and rebound_true < rebound_activation_threshold_kwh
        )
        pred_shifted_without_rebound = (
            shifted_pred >= shifted_threshold_kwh and rebound_pred < rebound_activation_threshold_kwh
        )
        daily_rows.append(
            {
                "run_dir": str(run_dir),
                "day": pd.Timestamp(day).date().isoformat(),
                "split_group_run": str(ordered["split_group_run"].iloc[0]),
                "is_test": bool(ordered["is_test"].iloc[0]),
                "season_regime": _season_regime(pd.Timestamp(day).month),
                "month": int(pd.Timestamp(day).month),
                "day_of_year": int(pd.Timestamp(day).dayofyear),
                "q_ref_sum_kwh": float(q_ref.sum()),
                "q_ref_peak_kw": float(q_ref.max()),
                "t_outdoor_mean_c": float(pd.to_numeric(ordered["t_outdoor_c"], errors="raise").mean()),
                **_daily_state_features(ordered=ordered, q_ref=q_ref),
                "shifted_true_kwh": shifted_true,
                "rebound_true_kwh": rebound_true,
                "peak_true_kw": peak_true,
                "shifted_pred_kwh": shifted_pred,
                "rebound_pred_kwh": rebound_pred,
                "peak_pred_kw": peak_pred,
                "true_rebound_active": bool(true_rebound_active),
                "pred_rebound_active": bool(pred_rebound_active),
                "true_shifted_without_rebound": bool(true_shifted_without_rebound),
                "pred_shifted_without_rebound": bool(pred_shifted_without_rebound),
                "trigger_state_mismatch": _trigger_state_mismatch(
                    true_shifted_without_rebound=true_shifted_without_rebound,
                    pred_shifted_without_rebound=pred_shifted_without_rebound,
                    true_rebound_active=true_rebound_active,
                    pred_rebound_active=pred_rebound_active,
                ),
                **{f"true_{key}": value for key, value in true_state.items()},
                **{f"pred_{key}": value for key, value in pred_state.items()},
            }
        )
        hourly_rows.append(
            _hourly_label_frame(
                run_dir=str(run_dir),
                day=pd.Timestamp(day).date().isoformat(),
                timestamps=q_ref.index,
                true_delta=true_delta,
                pred_delta=pred_delta,
                true_first_cutback_hour=int(true_state["first_cutback_hour"]),
                pred_first_cutback_hour=int(pred_state["first_cutback_hour"]),
                hourly_deadband_kwh=hourly_deadband_kwh,
                is_test=bool(ordered["is_test"].iloc[0]),
            )
        )
    daily = pd.DataFrame(daily_rows).sort_values(["day", "run_dir"]).reset_index(drop=True)
    daily = _add_lagged_daily_context_features(daily)
    hourly = pd.concat(hourly_rows, ignore_index=True).sort_values(["day", "hour_index"]).reset_index(drop=True)
    return daily, hourly


def _add_lagged_daily_context_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Add ex-ante previous-day context for thermal-state memory.

    Upper-only rebound depends on the building state at the start of the day.
    The hourly model already sees intra-day weather/load, but the daily router
    also needs a compact proxy for the preceding thermal history.  These fields
    are computed from the canonical Vienna daily context, not from ThermFlex
    outcomes, so they do not leak the target KPIs.
    """

    context = _build_daily_features(load_vienna_dh_thermflex_full_year_context()).reset_index()
    context["day"] = pd.to_datetime(context["date"], errors="raise").dt.date.astype(str)
    context = context.sort_values("day").reset_index(drop=True)
    context_columns = {
        "dh_space_heat_total_kwh": "space_heat_total_kwh",
        "t_outdoor_mean_c": "t_outdoor_mean_c",
        "t_outdoor_min_c": "t_outdoor_min_c",
        "t_outdoor_max_c": "t_outdoor_max_c",
        "mc_auction_mean_eur_mwh": "price_mean_eur_mwh",
        "mc_auction_peak_eur_mwh": "price_peak_eur_mwh",
        "irradiance_proxy_sum": "irradiance_sum",
        "solargains_proxy_sum": "solargains_sum",
    }
    missing = sorted(set(context_columns).difference(context.columns))
    if missing:
        raise KeyError("[upper_only_trigger_state_labels] lag context missing columns: " + ", ".join(missing))

    enriched = daily.copy()
    day_index = pd.to_datetime(enriched["day"], errors="raise")
    for lag_days in (1, 2, 3):
        lag = context.loc[:, ["day", *context_columns.keys()]].copy()
        lag["day"] = (pd.to_datetime(lag["day"], errors="raise") + pd.Timedelta(days=lag_days)).dt.date.astype(str)
        lag = lag.rename(
            columns={source: f"prev{lag_days}_{target}" for source, target in context_columns.items()}
        )
        enriched = enriched.merge(lag, on="day", how="left", validate="many_to_one")
        available_col = f"prev{lag_days}_context_available"
        lag_cols = [f"prev{lag_days}_{target}" for target in context_columns.values()]
        enriched[available_col] = (~enriched[lag_cols].isna().any(axis=1)).astype(int)
        for lag_col in lag_cols:
            current_name = _current_context_column_for_lag(lag_col)
            if current_name not in enriched.columns:
                raise KeyError(
                    "[upper_only_trigger_state_labels] current-day replacement column missing for lag feature: "
                    f"{current_name}"
                )
            # The availability flag makes this explicit: for year-boundary
            # rows where the full-year context has no previous day, the current
            # day value is carried only so numeric model inputs remain finite.
            enriched[lag_col] = enriched[lag_col].fillna(pd.to_numeric(enriched[current_name], errors="raise"))

    for target in context_columns.values():
        cols = [f"prev{lag_days}_{target}" for lag_days in (1, 2, 3)]
        enriched[f"prev3_mean_{target}"] = enriched.loc[:, cols].mean(axis=1)
        current_name = _current_context_column_for_target(target)
        if current_name in enriched.columns:
            enriched[f"current_minus_prev3_mean_{target}"] = (
                pd.to_numeric(enriched[current_name], errors="raise")
                - pd.to_numeric(enriched[f"prev3_mean_{target}"], errors="raise")
            )
    return enriched


def _current_context_column_for_lag(lag_column: str) -> str:
    """Map one previous-day feature to the matching current-day feature."""

    for prefix in ("prev1_", "prev2_", "prev3_"):
        if str(lag_column).startswith(prefix):
            return _current_context_column_for_target(str(lag_column)[len(prefix) :])
    raise ValueError(f"[upper_only_trigger_state_labels] unsupported lag feature name: {lag_column}")


def _current_context_column_for_target(target: str) -> str:
    """Map canonical daily-context names to existing daily label columns."""

    mapping = {
        "space_heat_total_kwh": "q_ref_sum_kwh",
        "t_outdoor_mean_c": "t_outdoor_mean_c",
        "t_outdoor_min_c": "t_outdoor_min_c",
        "t_outdoor_max_c": "t_outdoor_max_c",
        "price_mean_eur_mwh": "price_mean_eur_mwh",
        "price_peak_eur_mwh": "price_max_eur_mwh",
        "irradiance_sum": "irradiance_sum",
        "solargains_sum": "solargains_sum",
    }
    if target not in mapping:
        raise KeyError(f"[upper_only_trigger_state_labels] unsupported lag target: {target}")
    return mapping[target]


def _daily_state_features(*, ordered: pd.DataFrame, q_ref: pd.Series) -> dict[str, float | int]:
    """Summarize ex-ante daily state drivers that affect trigger timing.

    Upper-only rebound is dominated by whether the optimized sequence places a
    cutback early enough to create same-day recovery.  A single outdoor
    temperature mean is too weak for that distinction, so this contract exposes
    compact but explicit weather, reference-load and price-shape features.
    """

    by_timestamp = ordered.groupby("timestamp", sort=True)
    hourly = pd.DataFrame(
        {
            "q_ref_kwh": pd.to_numeric(q_ref, errors="raise"),
            "t_outdoor_c": pd.to_numeric(by_timestamp["t_outdoor_c"].mean(), errors="raise"),
            "mc_auction_eur_mwh": pd.to_numeric(by_timestamp["mc_auction_eur_mwh"].mean(), errors="raise"),
            "gas_price_eur_mwh_fuel": pd.to_numeric(
                by_timestamp["gas_price_eur_mwh_fuel"].mean(),
                errors="raise",
            ),
            "co2_price_eur_tco2": pd.to_numeric(by_timestamp["co2_price_eur_tco2"].mean(), errors="raise"),
            "irradiance_proxy": pd.to_numeric(by_timestamp["irradiance_proxy"].mean(), errors="raise"),
            "solargains_proxy": pd.to_numeric(by_timestamp["solargains_proxy"].mean(), errors="raise"),
        }
    ).sort_index()
    if len(hourly) != 24:
        raise ValueError("[upper_only_trigger_state_labels] daily state features require exactly 24 hours.")

    hours = pd.to_datetime(hourly.index, errors="raise").hour.to_numpy(dtype=int)
    out: dict[str, float | int] = {
        "q_ref_peak_hour": int(hours[int(np.argmax(hourly["q_ref_kwh"].to_numpy(dtype=float)))]),
        "price_peak_hour": int(hours[int(np.argmax(hourly["mc_auction_eur_mwh"].to_numpy(dtype=float)))]),
        "price_low_hour": int(hours[int(np.argmin(hourly["mc_auction_eur_mwh"].to_numpy(dtype=float)))]),
        "t_outdoor_min_c": float(hourly["t_outdoor_c"].min()),
        "t_outdoor_max_c": float(hourly["t_outdoor_c"].max()),
        "t_outdoor_std_c": float(hourly["t_outdoor_c"].std(ddof=0)),
        "heating_degree_hours_15c": float(np.maximum(15.0 - hourly["t_outdoor_c"].to_numpy(dtype=float), 0.0).sum()),
        "price_mean_eur_mwh": float(hourly["mc_auction_eur_mwh"].mean()),
        "price_min_eur_mwh": float(hourly["mc_auction_eur_mwh"].min()),
        "price_max_eur_mwh": float(hourly["mc_auction_eur_mwh"].max()),
        "price_std_eur_mwh": float(hourly["mc_auction_eur_mwh"].std(ddof=0)),
        "price_spread_eur_mwh": float(hourly["mc_auction_eur_mwh"].max() - hourly["mc_auction_eur_mwh"].min()),
        "gas_price_mean_eur_mwh_fuel": float(hourly["gas_price_eur_mwh_fuel"].mean()),
        "co2_price_mean_eur_tco2": float(hourly["co2_price_eur_tco2"].mean()),
        "irradiance_sum": float(hourly["irradiance_proxy"].sum()),
        "solargains_sum": float(hourly["solargains_proxy"].sum()),
    }
    for block_name, mask in _hour_block_masks(hours).items():
        q_ref_block = hourly.loc[mask, "q_ref_kwh"]
        price_block = hourly.loc[mask, "mc_auction_eur_mwh"]
        temp_block = hourly.loc[mask, "t_outdoor_c"]
        out[f"q_ref_{block_name}_sum_kwh"] = float(q_ref_block.sum())
        out[f"q_ref_{block_name}_share"] = float(q_ref_block.sum() / max(float(hourly["q_ref_kwh"].sum()), 1e-12))
        out[f"price_{block_name}_mean_eur_mwh"] = float(price_block.mean())
        out[f"t_outdoor_{block_name}_mean_c"] = float(temp_block.mean())
    out["price_late_minus_midday_eur_mwh"] = float(
        out["price_late_mean_eur_mwh"] - out["price_midday_mean_eur_mwh"]
    )
    out["price_evening_minus_morning_eur_mwh"] = float(
        out["price_evening_mean_eur_mwh"] - out["price_morning_mean_eur_mwh"]
    )
    out["t_late_minus_morning_c"] = float(out["t_outdoor_late_mean_c"] - out["t_outdoor_morning_mean_c"])
    return out


def _hour_block_masks(hours: np.ndarray) -> dict[str, np.ndarray]:
    """Return stable intraday blocks used by Upper-only timing diagnostics."""

    return {
        "night": (hours >= 0) & (hours <= 5),
        "morning": (hours >= 6) & (hours <= 10),
        "midday": (hours >= 11) & (hours <= 16),
        "evening": (hours >= 17) & (hours <= 20),
        "late": (hours >= 21) & (hours <= 23),
    }


def _sequence_state(delta: np.ndarray, *, hourly_deadband_kwh: float) -> dict[str, float | int | bool]:
    """Summarize the cutback/positive-tail structure of one daily delta series."""

    values = np.asarray(delta, dtype=float)
    if values.size != 24:
        raise ValueError("[upper_only_trigger_state_labels] expected exactly 24 hourly deltas per day.")
    deadband = float(hourly_deadband_kwh)
    cutback_mask = values <= -deadband
    first_cutback = int(np.argmax(cutback_mask)) if bool(cutback_mask.any()) else -1
    positive = np.maximum(values, 0.0)
    negative = np.maximum(-values, 0.0)
    after_cutback_mask = np.zeros(values.shape, dtype=bool)
    if first_cutback >= 0:
        after_cutback_mask[np.arange(values.size) > first_cutback] = True
    return {
        "has_cutback_trigger": bool(first_cutback >= 0),
        "first_cutback_hour": int(first_cutback),
        "positive_mass_kwh": float(np.sum(positive)),
        "negative_mass_kwh": float(np.sum(negative)),
        "positive_after_cutback_kwh": float(np.sum(positive[after_cutback_mask])),
        "positive_before_cutback_kwh": float(np.sum(positive[~after_cutback_mask])),
        "cutback_hour_count": int(np.sum(cutback_mask)),
        "positive_hour_count": int(np.sum(values >= deadband)),
        "peak_positive_kwh": float(np.max(positive)),
        "peak_negative_kwh": float(np.max(negative)),
    }


def _hourly_label_frame(
    *,
    run_dir: str,
    day: str,
    timestamps: pd.Index,
    true_delta: np.ndarray,
    pred_delta: np.ndarray,
    true_first_cutback_hour: int,
    pred_first_cutback_hour: int,
    hourly_deadband_kwh: float,
    is_test: bool,
) -> pd.DataFrame:
    """Create hourly masks that explain the daily trigger-state labels."""

    hour_index = np.arange(len(true_delta), dtype=int)
    true_after = true_first_cutback_hour >= 0 and hour_index > int(true_first_cutback_hour)
    pred_after = pred_first_cutback_hour >= 0 and hour_index > int(pred_first_cutback_hour)
    return pd.DataFrame(
        {
            "run_dir": run_dir,
            "day": day,
            "timestamp": pd.to_datetime(timestamps).astype(str),
            "hour_index": hour_index,
            "is_test": bool(is_test),
            "true_delta_kwh": np.asarray(true_delta, dtype=float),
            "pred_delta_kwh": np.asarray(pred_delta, dtype=float),
            "true_is_cutback": np.asarray(true_delta, dtype=float) <= -float(hourly_deadband_kwh),
            "pred_is_cutback": np.asarray(pred_delta, dtype=float) <= -float(hourly_deadband_kwh),
            "true_is_positive_after_cutback": true_after & (np.asarray(true_delta, dtype=float) > float(hourly_deadband_kwh)),
            "pred_is_positive_after_cutback": pred_after & (np.asarray(pred_delta, dtype=float) > float(hourly_deadband_kwh)),
        }
    )


def _trigger_state_mismatch(
    *,
    true_shifted_without_rebound: bool,
    pred_shifted_without_rebound: bool,
    true_rebound_active: bool,
    pred_rebound_active: bool,
) -> str:
    """Classify the daily state error into action-oriented buckets."""

    if true_shifted_without_rebound and pred_rebound_active:
        return "false_active_on_shifted_without_rebound"
    if true_rebound_active and not pred_rebound_active:
        return "missed_rebound_active"
    if true_rebound_active and pred_rebound_active:
        return "active_match"
    if true_shifted_without_rebound and pred_shifted_without_rebound:
        return "shifted_without_rebound_match"
    if not true_rebound_active and not pred_rebound_active:
        return "inactive_match"
    return "other_mismatch"


def _label_counts(daily: pd.DataFrame) -> dict[str, Any]:
    """Return compact label counts for all rows and the persisted holdout."""

    rows: dict[str, Any] = {}
    for label, subset in (("all", daily), ("test", daily.loc[daily["is_test"].astype(bool)])):
        rows[label] = {
            "days": int(len(subset)),
            "true_rebound_active": int(subset["true_rebound_active"].sum()),
            "true_shifted_without_rebound": int(subset["true_shifted_without_rebound"].sum()),
            "true_has_cutback_trigger": int(subset["true_has_cutback_trigger"].sum()),
            "mismatch_counts": subset["trigger_state_mismatch"].value_counts().to_dict(),
        }
    return rows


def _prediction_quality(daily: pd.DataFrame) -> dict[str, Any]:
    """Summarize how well current predictions match the explicit state labels."""

    out: dict[str, Any] = {}
    for label, subset in (("all", daily), ("test", daily.loc[daily["is_test"].astype(bool)])):
        if subset.empty:
            continue
        true_active = subset["true_rebound_active"].astype(bool).to_numpy()
        pred_active = subset["pred_rebound_active"].astype(bool).to_numpy()
        true_cutback = subset["true_has_cutback_trigger"].astype(bool).to_numpy()
        pred_cutback = subset["pred_has_cutback_trigger"].astype(bool).to_numpy()
        out[label] = {
            "rebound_active_accuracy": float(accuracy_score(true_active, pred_active)),
            "rebound_active_f1": float(f1_score(true_active, pred_active, zero_division=0)),
            "cutback_trigger_accuracy": float(accuracy_score(true_cutback, pred_cutback)),
            "cutback_trigger_f1": float(f1_score(true_cutback, pred_cutback, zero_division=0)),
            "positive_after_cutback_r2": _safe_r2(
                subset["true_positive_after_cutback_kwh"].to_numpy(dtype=float),
                subset["pred_positive_after_cutback_kwh"].to_numpy(dtype=float),
            ),
            "positive_after_cutback_mae": float(
                mean_absolute_error(
                    subset["true_positive_after_cutback_kwh"].to_numpy(dtype=float),
                    subset["pred_positive_after_cutback_kwh"].to_numpy(dtype=float),
                )
            ),
        }
    return out


def _worst_test_days(daily: pd.DataFrame) -> list[dict[str, Any]]:
    """List the largest state/magnitude misses on the persisted holdout."""

    test = daily.loc[daily["is_test"].astype(bool)].copy()
    if test.empty:
        return []
    test["positive_after_abs_error_kwh"] = (
        test["pred_positive_after_cutback_kwh"] - test["true_positive_after_cutback_kwh"]
    ).abs()
    columns = [
        "day",
        "season_regime",
        "trigger_state_mismatch",
        "shifted_true_kwh",
        "rebound_true_kwh",
        "rebound_pred_kwh",
        "true_first_cutback_hour",
        "pred_first_cutback_hour",
        "true_positive_after_cutback_kwh",
        "pred_positive_after_cutback_kwh",
        "positive_after_abs_error_kwh",
    ]
    return test.sort_values("positive_after_abs_error_kwh", ascending=False).head(12)[columns].to_dict(orient="records")


def _validate_inputs(
    *,
    frame: pd.DataFrame,
    rebound_activation_threshold_kwh: float,
    shifted_threshold_kwh: float,
    hourly_deadband_kwh: float,
) -> None:
    """Validate the explicit diagnostic contract before exporting labels."""

    required = {
        "run_dir",
        "day",
        "timestamp",
        "split_group_run",
        "cohort_key",
        "cohort_q_heat_ref_kwh",
        "cohort_q_heat_kwh",
        "q_delta_pred_kwh",
        "t_outdoor_c",
        "mc_auction_eur_mwh",
        "gas_price_eur_mwh_fuel",
        "co2_price_eur_tco2",
        "irradiance_proxy",
        "solargains_proxy",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError("[upper_only_trigger_state_labels] missing required columns: " + ", ".join(missing))
    for name, value in {
        "rebound_activation_threshold_kwh": rebound_activation_threshold_kwh,
        "shifted_threshold_kwh": shifted_threshold_kwh,
        "hourly_deadband_kwh": hourly_deadband_kwh,
    }.items():
        numeric = float(value)
        if not np.isfinite(numeric) or numeric < 0.0:
            raise ValueError(f"[upper_only_trigger_state_labels] {name} must be finite and non-negative.")


def _season_regime(month: int) -> str:
    """Keep the same coarse regimes as the existing Upper-only diagnostics."""

    month_int = int(month)
    if month_int in {12, 1, 2}:
        return "winter"
    if month_int in {3, 4, 10, 11}:
        return "shoulder"
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--rebound-activation-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--shifted-threshold-kwh", type=float, default=1_000_000.0)
    parser.add_argument("--hourly-deadband-kwh", type=float, default=1_000.0)
    args = parser.parse_args()
    result = build_upper_only_trigger_state_labels(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        rebound_activation_threshold_kwh=float(args.rebound_activation_threshold_kwh),
        shifted_threshold_kwh=float(args.shifted_threshold_kwh),
        hourly_deadband_kwh=float(args.hourly_deadband_kwh),
    )
    print(json.dumps({"output_dir": str(result.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
