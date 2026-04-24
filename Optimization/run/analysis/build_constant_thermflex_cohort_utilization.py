from __future__ import annotations

"""Build an explicit cohort-utilization bundle for constant thermflex cases.

This module is intentionally narrow in scope:
- it replays already solved gold runs with the same fixed design vector,
- it consumes the explicit coupled-dispatch member outputs,
- it aggregates them by cohort/building key,
- it writes one hourly export, one cohort summary, and one compact plot sheet.

The goal is to answer one paper-relevant question:
"Which cohorts actually use additional global duration/event freedom?"
"""

import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

from Optimization.framework.engines.Gold.gold_engine import GoldEngine
from Settings import get_settings
from dispatch.metrics import compute_thermflex_series_metrics


def build_constant_thermflex_cohort_utilization_bundle(
    *,
    output_dir: Path,
    case_specs: list[dict[str, str]],
) -> Path:
    """Replay selected constant-thermflex runs and export cohort utilization.

    The replay uses the explicit `X_opt.npy` stored in each gold run directory.
    This keeps the analysis reproducible and avoids inventing a second source
    for the fixed design point.
    """

    output_dir = Path(output_dir).resolve()
    hourly_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for spec in case_specs:
        label = str(spec["label"])
        if label == "constant_no_thermflex":
            # The baseline has thermflex disabled, so no member-level thermflex
            # arrays exist there. It remains the reference in the main KPI
            # comparison, but it is not part of the utilization bundle.
            continue
        run_dir = Path(spec["run_dir"]).resolve()
        override_path = Path(spec["override_path"]).resolve()
        settings = _load_settings(override_path)
        raw_results = _replay_raw_results(run_dir=run_dir, settings=settings)
        case_hourly, case_summary = _build_case_tables(
            case_label=label,
            run_dir=run_dir,
            settings=settings,
            raw_results=raw_results,
        )
        hourly_rows.extend(case_hourly)
        summary_rows.extend(case_summary)

    if not hourly_rows:
        raise ValueError("[constant_thermflex_cohort_utilization] No hourly cohort rows were produced.")
    if not summary_rows:
        raise ValueError("[constant_thermflex_cohort_utilization] No cohort summary rows were produced.")

    hourly_df = pd.DataFrame(hourly_rows)
    summary_df = pd.DataFrame(summary_rows)
    hourly_df.to_csv(output_dir / "constant_thermflex_cohort_utilization_hourly.csv", index=False)
    summary_df.to_csv(output_dir / "constant_thermflex_cohort_utilization_summary.csv", index=False)

    summary_payload = {
        "cases_evaluated": sorted(summary_df["case_label"].astype(str).unique().tolist()),
        "cohorts_evaluated": sorted(summary_df["cohort_key"].astype(str).unique().tolist()),
        "duration_trend_cases_lb21_evt1": sorted(
            summary_df.loc[
                (summary_df["thermflex_constant_lower_bound_c"] == 21.0)
                & (summary_df["thermflex_max_events_per_day"] == 1),
                "case_label",
            ]
            .astype(str)
            .unique()
            .tolist(),
            key=_duration_sort_key,
        ),
        "upper_only_cases": sorted(
            summary_df.loc[
                summary_df["thermflex_constant_lower_bound_c"] == 22.5,
                "case_label",
            ]
            .astype(str)
            .unique()
            .tolist(),
        ),
    }
    (output_dir / "constant_thermflex_cohort_utilization_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown_summary(output_dir=output_dir, summary_df=summary_df)
    _save_plot(output_dir=output_dir, summary_df=summary_df)
    return output_dir


def _load_settings(override_path: Path) -> Any:
    if not override_path.exists():
        raise FileNotFoundError(
            f"[constant_thermflex_cohort_utilization] override file not found: {override_path}"
        )
    overrides = json.loads(override_path.read_text(encoding="utf-8-sig"))
    return get_settings(overrides=overrides)


def _replay_raw_results(*, run_dir: Path, settings: Any) -> dict[str, Any]:
    x_path = run_dir / "X_opt.npy"
    if not x_path.exists():
        raise FileNotFoundError(
            f"[constant_thermflex_cohort_utilization] X_opt.npy not found: {x_path}"
        )
    x = np.asarray(np.load(x_path), dtype=float)
    if x.ndim == 2:
        if x.shape[0] < 1:
            raise ValueError(
                f"[constant_thermflex_cohort_utilization] X_opt.npy is empty in {run_dir}."
            )
        x = x[0]
    x = x.reshape(-1)
    teacher = GoldEngine(settings)
    _f, _g, _flows, raw_results = teacher.evaluate_one_with_details(x)
    if not isinstance(raw_results, dict):
        raise TypeError(
            f"[constant_thermflex_cohort_utilization] Gold replay did not return a raw-results dict for {run_dir}."
        )
    return raw_results


def _require_member_matrix(raw_results: dict[str, Any], key: str, *, rows: int, cols: int) -> np.ndarray:
    if key not in raw_results:
        raise KeyError(
            f"[constant_thermflex_cohort_utilization] raw_results['{key}'] is required for cohort analysis."
        )
    arr = np.asarray(raw_results[key], dtype=float)
    if arr.shape != (rows, cols):
        raise ValueError(
            f"[constant_thermflex_cohort_utilization] raw_results['{key}'] has shape {arr.shape}, "
            f"expected {(rows, cols)}."
        )
    return arr


def _require_member_labels(raw_results: dict[str, Any], key: str, *, expected: int) -> list[str]:
    if key not in raw_results:
        raise KeyError(
            f"[constant_thermflex_cohort_utilization] raw_results['{key}'] is required for cohort analysis."
        )
    values = raw_results[key]
    if isinstance(values, np.ndarray):
        flat = values.reshape(-1).tolist()
    elif isinstance(values, (list, tuple)):
        flat = list(values)
    else:
        raise TypeError(
            f"[constant_thermflex_cohort_utilization] raw_results['{key}'] must be list-like."
        )
    if len(flat) != expected:
        raise ValueError(
            f"[constant_thermflex_cohort_utilization] raw_results['{key}'] length {len(flat)} "
            f"does not match expected member count {expected}."
        )
    return [str(item) for item in flat]


def _build_case_tables(
    *,
    case_label: str,
    run_dir: Path,
    settings: Any,
    raw_results: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    timestamps = pd.to_datetime(np.asarray(raw_results.get("timestamps")))
    if timestamps.size == 0:
        raise ValueError(
            f"[constant_thermflex_cohort_utilization] raw_results['timestamps'] is empty for {case_label}."
        )
    member_count = int(
        raw_results.get("dispatch_diagnostics", {}).get("thermflex_member_count", 0) or 0
    )
    if member_count <= 0:
        raise ValueError(
            f"[constant_thermflex_cohort_utilization] thermflex_member_count must be > 0 for {case_label}."
        )
    n_steps = int(timestamps.size)
    cohort_keys = _require_member_labels(
        raw_results,
        "thermflex_member_building_keys",
        expected=member_count,
    )
    archetype_keys = _require_member_labels(
        raw_results,
        "thermflex_member_archetype_keys",
        expected=member_count,
    )
    member_ids = _require_member_labels(
        raw_results,
        "thermflex_member_ids",
        expected=member_count,
    )
    floor_area = np.asarray(raw_results.get("thermflex_member_floor_area_m2"), dtype=float).reshape(-1)
    if floor_area.size != member_count or np.any(~np.isfinite(floor_area)) or np.any(floor_area <= 0.0):
        raise ValueError(
            f"[constant_thermflex_cohort_utilization] thermflex_member_floor_area_m2 invalid for {case_label}."
        )
    q_heat = _require_member_matrix(
        raw_results,
        "thermflex_member_q_heat_kwh",
        rows=member_count,
        cols=n_steps,
    )
    q_ref = _require_member_matrix(
        raw_results,
        "thermflex_member_q_heat_ref_kwh",
        rows=member_count,
        cols=n_steps,
    )
    flex_active = _require_member_matrix(
        raw_results,
        "thermflex_member_flex_active",
        rows=member_count,
        cols=n_steps,
    )
    event_start = _require_member_matrix(
        raw_results,
        "thermflex_member_event_start",
        rows=member_count,
        cols=n_steps,
    )
    violation = _require_member_matrix(
        raw_results,
        "thermflex_member_temp_violation_degree_h",
        rows=member_count,
        cols=n_steps,
    )
    t_in = _require_member_matrix(
        raw_results,
        "thermflex_member_t_in_c",
        rows=member_count,
        cols=n_steps,
    )
    preheat_extra = _require_member_matrix(
        raw_results,
        "thermflex_member_event_preheat_extra_kwh",
        rows=member_count,
        cols=n_steps,
    )
    cutback_shed = _require_member_matrix(
        raw_results,
        "thermflex_member_event_cutback_shed_kwh",
        rows=member_count,
        cols=n_steps,
    )

    thermflex_cfg = settings.constraints.thermflex
    lower_bound_c = float(getattr(thermflex_cfg, "constant_lower_bound_c", 0.0) or 0.0)
    max_duration_h = int(getattr(thermflex_cfg, "max_flex_duration_h", 0) or 0)
    max_events_per_day = int(getattr(thermflex_cfg, "max_flex_events_per_day", 0) or 0)

    cohort_to_indices: dict[str, list[int]] = {}
    cohort_to_archetypes: dict[str, list[str]] = {}
    for member_idx, cohort_key in enumerate(cohort_keys):
        cohort_to_indices.setdefault(cohort_key, []).append(member_idx)
        cohort_to_archetypes.setdefault(cohort_key, []).append(archetype_keys[member_idx])

    hourly_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for cohort_key in sorted(cohort_to_indices.keys()):
        idxs = np.asarray(cohort_to_indices[cohort_key], dtype=int)
        weights = floor_area[idxs]
        cohort_q_heat = np.sum(q_heat[idxs, :], axis=0)
        cohort_q_ref = np.sum(q_ref[idxs, :], axis=0)
        cohort_q_delta = cohort_q_heat - cohort_q_ref
        cohort_active_count = np.sum(flex_active[idxs, :], axis=0)
        cohort_event_start_count = np.sum(event_start[idxs, :], axis=0)
        cohort_violation = np.sum(violation[idxs, :], axis=0)
        cohort_preheat_extra = np.sum(preheat_extra[idxs, :], axis=0)
        cohort_cutback_shed = np.sum(cutback_shed[idxs, :], axis=0)
        cohort_t_in_weighted = np.average(t_in[idxs, :], axis=0, weights=weights)
        cohort_t_in_min = np.min(t_in[idxs, :], axis=0)
        cohort_t_in_max = np.max(t_in[idxs, :], axis=0)
        cohort_member_count = int(idxs.size)
        cohort_floor_area_m2 = float(np.sum(weights))
        cohort_metrics = compute_thermflex_series_metrics(cohort_q_heat, cohort_q_ref)
        active_member_hours_total = float(np.sum(cohort_active_count))
        event_starts_total = float(np.sum(cohort_event_start_count))
        duration_cap_total = float(cohort_member_count * max_duration_h)
        event_cap_total = float(cohort_member_count * max_events_per_day)

        for step_idx, timestamp in enumerate(timestamps):
            hourly_rows.append(
                {
                    "case_label": case_label,
                    "run_dir": str(run_dir),
                    "timestamp": str(timestamp),
                    "cohort_key": cohort_key,
                    "cohort_member_count": cohort_member_count,
                    "cohort_floor_area_m2": cohort_floor_area_m2,
                    "thermflex_constant_lower_bound_c": lower_bound_c,
                    "thermflex_max_flex_duration_h": max_duration_h,
                    "thermflex_max_events_per_day": max_events_per_day,
                    "cohort_q_heat_kwh": float(cohort_q_heat[step_idx]),
                    "cohort_q_heat_ref_kwh": float(cohort_q_ref[step_idx]),
                    "cohort_q_delta_kwh": float(cohort_q_delta[step_idx]),
                    "cohort_flex_active_member_count": float(cohort_active_count[step_idx]),
                    "cohort_flex_active_member_share": float(cohort_active_count[step_idx] / cohort_member_count),
                    "cohort_event_start_count": float(cohort_event_start_count[step_idx]),
                    "cohort_temperature_violation_degree_h": float(cohort_violation[step_idx]),
                    "cohort_t_in_weighted_mean_c": float(cohort_t_in_weighted[step_idx]),
                    "cohort_t_in_member_min_c": float(cohort_t_in_min[step_idx]),
                    "cohort_t_in_member_max_c": float(cohort_t_in_max[step_idx]),
                    "cohort_preheat_extra_kwh": float(cohort_preheat_extra[step_idx]),
                    "cohort_cutback_shed_kwh": float(cohort_cutback_shed[step_idx]),
                }
            )

        summary_rows.append(
            {
                "case_label": case_label,
                "run_dir": str(run_dir),
                "cohort_key": cohort_key,
                "cohort_archetype_keys": "|".join(sorted(set(cohort_to_archetypes[cohort_key]))),
                "cohort_member_ids": "|".join(member_ids[idx] for idx in idxs),
                "cohort_member_count": cohort_member_count,
                "cohort_floor_area_m2": cohort_floor_area_m2,
                "thermflex_constant_lower_bound_c": lower_bound_c,
                "thermflex_max_flex_duration_h": max_duration_h,
                "thermflex_max_events_per_day": max_events_per_day,
                "cohort_shifted_space_heat_kwh": float(cohort_metrics["thermflex_shifted_space_heat_kwh"]),
                "cohort_additional_space_heat_kwh": float(cohort_metrics["thermflex_additional_space_heat_kwh"]),
                "cohort_rebound_kwh": float(cohort_metrics["thermflex_rebound_kwh"]),
                "cohort_peak_change_kw": float(cohort_metrics["thermflex_peak_change_kw"]),
                "cohort_effective_thermal_storage_kwh": float(
                    cohort_metrics["thermflex_effective_thermal_storage_kwh"]
                ),
                "cohort_active_member_hours_total": active_member_hours_total,
                "cohort_active_duration_cap_utilization": (
                    float(active_member_hours_total / duration_cap_total) if duration_cap_total > 0.0 else None
                ),
                "cohort_event_starts_total": event_starts_total,
                "cohort_event_cap_utilization": (
                    float(event_starts_total / event_cap_total) if event_cap_total > 0.0 else None
                ),
                "cohort_temperature_violation_degree_hours_total": float(np.sum(cohort_violation)),
                "cohort_t_in_weighted_mean_c": float(np.mean(cohort_t_in_weighted)),
                "cohort_t_in_weighted_min_c": float(np.min(cohort_t_in_weighted)),
                "cohort_t_in_weighted_max_c": float(np.max(cohort_t_in_weighted)),
                "cohort_t_in_member_min_c": float(np.min(cohort_t_in_min)),
                "cohort_t_in_member_max_c": float(np.max(cohort_t_in_max)),
                "cohort_preheat_extra_realized_kwh": float(np.sum(cohort_preheat_extra)),
                "cohort_cutback_shed_realized_kwh": float(np.sum(cohort_cutback_shed)),
            }
        )
    return hourly_rows, summary_rows


def _duration_sort_key(case_label: str) -> tuple[int, str]:
    digits = "".join(ch if ch.isdigit() else " " for ch in case_label)
    ints = [int(token) for token in digits.split() if token.strip()]
    return (ints[0] if ints else 9999, case_label)


def _write_markdown_summary(*, output_dir: Path, summary_df: pd.DataFrame) -> None:
    duration_df = summary_df[
        (summary_df["thermflex_constant_lower_bound_c"] == 21.0)
        & (summary_df["thermflex_max_events_per_day"] == 1)
    ].copy()
    duration_df = duration_df.sort_values(
        by=["cohort_key", "thermflex_max_flex_duration_h"],
        ascending=[True, True],
    )
    lines = [
        "# Constant Thermflex Cohort Utilization",
        "",
        "This bundle replays the explicit constant-reference thermflex gold runs and aggregates the coupled dispatch member outputs by cohort/building key.",
        "",
        "Duration-trend cohorts (`lower=21.0 C`, `events=1`):",
    ]
    for cohort_key in sorted(duration_df["cohort_key"].astype(str).unique().tolist()):
        cohort_slice = duration_df.loc[duration_df["cohort_key"] == cohort_key]
        cells = []
        for row in cohort_slice.itertuples(index=False):
            cells.append(
                f"`dur={int(row.thermflex_max_flex_duration_h)}h`: "
                f"`shifted={row.cohort_shifted_space_heat_kwh / 1e3:.1f} MWh`, "
                f"`active_cap={0.0 if pd.isna(row.cohort_active_duration_cap_utilization) else row.cohort_active_duration_cap_utilization:.3f}`, "
                f"`event_cap={0.0 if pd.isna(row.cohort_event_cap_utilization) else row.cohort_event_cap_utilization:.3f}`"
            )
        lines.append(f"- `{cohort_key}`: " + "; ".join(cells))
    (output_dir / "constant_thermflex_cohort_utilization_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _save_plot(*, output_dir: Path, summary_df: pd.DataFrame) -> None:
    duration_df = summary_df[
        (summary_df["thermflex_constant_lower_bound_c"] == 21.0)
        & (summary_df["thermflex_max_events_per_day"] == 1)
    ].copy()
    duration_df = duration_df.sort_values(
        by=["thermflex_max_flex_duration_h", "cohort_key"],
        ascending=[True, True],
    )
    upper_only_df = summary_df[
        summary_df["case_label"].isin(
            ["lb22p5_dur4_evt1_upper_only", "lb22p5_dur24_evt24_upper_only_proxy"]
        )
    ].copy()
    upper_only_df = upper_only_df.sort_values(by=["case_label", "cohort_key"], ascending=[True, True])

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    if not duration_df.empty:
        for cohort_key in sorted(duration_df["cohort_key"].astype(str).unique().tolist()):
            cohort_slice = duration_df.loc[duration_df["cohort_key"] == cohort_key]
            axes[0, 0].plot(
                cohort_slice["thermflex_max_flex_duration_h"],
                cohort_slice["cohort_shifted_space_heat_kwh"] / 1e3,
                marker="o",
                label=cohort_key,
            )
            axes[0, 1].plot(
                cohort_slice["thermflex_max_flex_duration_h"],
                cohort_slice["cohort_active_duration_cap_utilization"],
                marker="o",
                label=cohort_key,
            )
            axes[1, 0].plot(
                cohort_slice["thermflex_max_flex_duration_h"],
                cohort_slice["cohort_event_cap_utilization"],
                marker="o",
                label=cohort_key,
            )
        axes[0, 0].set_title("Cohort Shifted Energy vs Duration")
        axes[0, 0].set_ylabel("MWh / slice")
        axes[0, 0].grid(True, axis="y", alpha=0.3)
        axes[0, 1].set_title("Duration-Cap Utilization by Cohort")
        axes[0, 1].set_ylabel("share of member-hour cap")
        axes[0, 1].set_ylim(0.0, 1.05)
        axes[0, 1].grid(True, axis="y", alpha=0.3)
        axes[1, 0].set_title("Event-Cap Utilization by Cohort")
        axes[1, 0].set_xlabel("max_flex_duration_h")
        axes[1, 0].set_ylabel("share of member-event cap")
        axes[1, 0].set_ylim(0.0, 1.05)
        axes[1, 0].grid(True, axis="y", alpha=0.3)
        axes[0, 0].legend(fontsize=8, ncol=2)
    if not upper_only_df.empty:
        plot_df = upper_only_df.pivot(
            index="cohort_key",
            columns="case_label",
            values="cohort_shifted_space_heat_kwh",
        ).fillna(0.0)
        plot_df = plot_df / 1e3
        plot_df.plot(
            kind="bar",
            ax=axes[1, 1],
            color=["#34495e", "#e67e22"],
            width=0.75,
        )
        axes[1, 1].set_title("Upper-Only Cases by Cohort")
        axes[1, 1].set_ylabel("Shifted MWh / slice")
        axes[1, 1].tick_params(axis="x", rotation=25)
        axes[1, 1].grid(True, axis="y", alpha=0.3)
        axes[1, 1].legend(fontsize=8)
    else:
        axes[1, 1].set_axis_off()
    fig.tight_layout()
    fig.savefig(output_dir / "constant_thermflex_cohort_utilization.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
