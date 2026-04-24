from __future__ import annotations

"""Build a compact plot/data bundle for the constant thermflex isolation case.

The generic paper comparison is useful for broad case tables. This helper adds
an explicit thermflex-isolation view with only the metrics that matter for the
"constant reference, thermflex off vs on" question.

The output is intentionally small and explicit:
- one focused multi-panel plot,
- one compact markdown summary,
- one compact JSON delta summary.

There are no silent fallbacks:
- both required case labels must exist,
- all required KPI columns must exist,
- missing files raise explicit errors.
"""

import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

from Settings import get_settings
from Optimization.framework.engines.Gold.gold_engine import GoldEngine


REQUIRED_CASES = ("constant_no_thermflex", "constant_thermflex")
REQUIRED_COLUMNS = (
    "dispatch_operating_cost_eur",
    "dh_unserved_heat_kwh",
    "co2_emissions_total_t",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "grid_import_cost_eur",
    "fuel_cost_eur",
    "co2_cost_eur",
    "variable_opex_eur",
    "district_gas_boiler_generation_kwh",
    "district_gas_chp_thermal_generation_kwh",
    "district_heat_pump_generation_kwh",
)


def build_constant_thermflex_isolation_bundle(
    output_dir: Path,
    *,
    override_paths: dict[str, Path] | None = None,
) -> Path:
    output_dir = Path(output_dir).resolve()
    comparison_csv = output_dir / "paper_dispatch_comparison.csv"
    if not comparison_csv.exists():
        raise FileNotFoundError(
            f"[constant_thermflex_isolation] paper_dispatch_comparison.csv not found: {comparison_csv}"
        )

    df = pd.read_csv(comparison_csv)
    if "case_label" not in df.columns:
        raise KeyError("[constant_thermflex_isolation] case_label missing in paper comparison csv.")
    df = df.set_index("case_label")

    missing_cases = [label for label in REQUIRED_CASES if label not in df.index]
    if missing_cases:
        raise KeyError(
            "[constant_thermflex_isolation] Required cases missing in paper comparison csv: "
            + ", ".join(missing_cases)
        )

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise KeyError(
            "[constant_thermflex_isolation] Required KPI columns missing in paper comparison csv: "
            + ", ".join(missing_cols)
        )

    ref = df.loc["constant_no_thermflex"]
    flex = df.loc["constant_thermflex"]

    delta_summary = _build_delta_summary(ref=ref, flex=flex)
    _write_delta_summary(output_dir=output_dir, delta_summary=delta_summary)
    _save_focus_plot(output_dir=output_dir, ref=ref, flex=flex)
    if override_paths is not None:
        required_override_cases = [label for label in REQUIRED_CASES if label not in override_paths]
        if required_override_cases:
            raise KeyError(
                "[constant_thermflex_isolation] override paths missing for required cases: "
                + ", ".join(required_override_cases)
            )
        ref_series = _evaluate_case_timeseries(override_paths["constant_no_thermflex"])
        flex_series = _evaluate_case_timeseries(override_paths["constant_thermflex"])
        _write_timeseries_settings_summary(output_dir=output_dir, ref_series=ref_series, flex_series=flex_series)
        _save_timeseries_plot(output_dir=output_dir, ref_series=ref_series, flex_series=flex_series)
    return output_dir


def _pct_delta(flex_value: float, ref_value: float) -> float | None:
    if abs(ref_value) < 1e-12:
        return None
    return float(100.0 * (flex_value - ref_value) / ref_value)


def _build_delta_summary(*, ref: pd.Series, flex: pd.Series) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "baseline_case": "constant_no_thermflex",
        "comparison_case": "constant_thermflex",
        "metrics": {},
    }
    for col in (
        "dispatch_operating_cost_eur",
        "dh_unserved_heat_kwh",
        "co2_emissions_total_t",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_peak_change_kw",
        "grid_import_cost_eur",
        "fuel_cost_eur",
        "co2_cost_eur",
        "variable_opex_eur",
        "district_gas_boiler_generation_kwh",
        "district_gas_chp_thermal_generation_kwh",
        "district_heat_pump_generation_kwh",
    ):
        ref_value = float(ref[col])
        flex_value = float(flex[col])
        summary["metrics"][col] = {
            "constant_no_thermflex": ref_value,
            "constant_thermflex": flex_value,
            "delta": float(flex_value - ref_value),
            "pct_delta": _pct_delta(flex_value, ref_value),
        }

    shifted = float(flex["thermflex_shifted_space_heat_kwh"])
    rebound = float(flex["thermflex_rebound_kwh"])
    if shifted <= 0.0:
        raise ValueError(
            "[constant_thermflex_isolation] thermflex_shifted_space_heat_kwh must be positive for the thermflex case."
        )
    summary["derived"] = {
        "rebound_over_shifted_pct": float(100.0 * rebound / shifted),
    }
    return summary


def _write_delta_summary(*, output_dir: Path, delta_summary: dict[str, Any]) -> None:
    json_path = output_dir / "constant_thermflex_isolation_summary.json"
    md_path = output_dir / "constant_thermflex_isolation_summary.md"
    json_path.write_text(json.dumps(delta_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    metrics = delta_summary["metrics"]
    derived = delta_summary["derived"]
    lines = [
        "# Constant Thermflex Isolation Summary",
        "",
        "Comparison:",
        "- `constant_no_thermflex` vs `constant_thermflex`",
        "",
        "Key metrics:",
        f"- `dispatch_operating_cost_eur`: {metrics['dispatch_operating_cost_eur']['delta']:.6f} EUR "
        f"({metrics['dispatch_operating_cost_eur']['pct_delta']:.9f} %)",
        f"- `dh_unserved_heat_kwh`: {metrics['dh_unserved_heat_kwh']['delta']:.6f} kWh "
        f"({metrics['dh_unserved_heat_kwh']['pct_delta']:.6f} %)",
        f"- `co2_emissions_total_t`: {metrics['co2_emissions_total_t']['delta']:.6f} t "
        f"({metrics['co2_emissions_total_t']['pct_delta']:.6f} %)",
        f"- `thermflex_shifted_space_heat_kwh`: {metrics['thermflex_shifted_space_heat_kwh']['constant_thermflex']:.6f} kWh",
        f"- `thermflex_rebound_kwh`: {metrics['thermflex_rebound_kwh']['constant_thermflex']:.6f} kWh",
        f"- `thermflex_peak_change_kw`: {metrics['thermflex_peak_change_kw']['constant_thermflex']:.6f} kW",
        "",
        "Cost component deltas:",
        f"- `grid_import_cost_eur`: {metrics['grid_import_cost_eur']['delta']:.6f} EUR",
        f"- `fuel_cost_eur`: {metrics['fuel_cost_eur']['delta']:.6f} EUR",
        f"- `co2_cost_eur`: {metrics['co2_cost_eur']['delta']:.6f} EUR",
        f"- `variable_opex_eur`: {metrics['variable_opex_eur']['delta']:.6f} EUR",
        "",
        "Dispatch mix deltas:",
        f"- `district_gas_boiler_generation_kwh`: {metrics['district_gas_boiler_generation_kwh']['delta']:.6f} kWh",
        f"- `district_gas_chp_thermal_generation_kwh`: {metrics['district_gas_chp_thermal_generation_kwh']['delta']:.6f} kWh",
        f"- `district_heat_pump_generation_kwh`: {metrics['district_heat_pump_generation_kwh']['delta']:.6f} kWh",
        "",
        f"- `rebound_over_shifted_pct`: {derived['rebound_over_shifted_pct']:.6f} %",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _save_focus_plot(*, output_dir: Path, ref: pd.Series, flex: pd.Series) -> None:
    case_labels = ["constant_no_thermflex", "constant_thermflex"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))

    _plot_pair_bar(
        axes[0, 0],
        case_labels,
        [float(ref["dispatch_operating_cost_eur"]) / 1e6, float(flex["dispatch_operating_cost_eur"]) / 1e6],
        ylabel="EUR million / slice",
        title="Operating Cost",
    )
    _plot_pair_bar(
        axes[0, 1],
        case_labels,
        [float(ref["dh_unserved_heat_kwh"]) / 1e3, float(flex["dh_unserved_heat_kwh"]) / 1e3],
        ylabel="MWh / slice",
        title="Unserved Heat",
    )
    _plot_pair_bar(
        axes[0, 2],
        case_labels,
        [float(ref["co2_emissions_total_t"]), float(flex["co2_emissions_total_t"])],
        ylabel="t CO2 / slice",
        title="Operational CO2",
    )
    _plot_pair_bar(
        axes[1, 0],
        case_labels,
        [float(ref["thermflex_shifted_space_heat_kwh"]) / 1e3, float(flex["thermflex_shifted_space_heat_kwh"]) / 1e3],
        ylabel="MWh / slice",
        title="Shifted Heat",
    )
    _plot_pair_bar(
        axes[1, 1],
        case_labels,
        [float(ref["thermflex_rebound_kwh"]) / 1e3, float(flex["thermflex_rebound_kwh"]) / 1e3],
        ylabel="MWh / slice",
        title="Rebound",
    )
    _plot_pair_bar(
        axes[1, 2],
        case_labels,
        [float(ref["thermflex_peak_change_kw"]) / 1e3, float(flex["thermflex_peak_change_kw"]) / 1e3],
        ylabel="MW / slice",
        title="Peak Change",
    )

    fig.tight_layout()
    fig.savefig(output_dir / "constant_thermflex_isolation.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_pair_bar(ax: Any, labels: list[str], values: list[float], *, ylabel: str, title: str) -> None:
    ax.bar(labels, values, color=["#7f8c8d", "#c0392b"])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=15)


def _evaluate_case_timeseries(override_path: Path) -> dict[str, Any]:
    override_path = Path(override_path).resolve()
    if not override_path.exists():
        raise FileNotFoundError(f"[constant_thermflex_isolation] Override file not found: {override_path}")

    overrides = json.loads(override_path.read_text(encoding="utf-8-sig"))
    cfg = get_settings(overrides=overrides)
    engine = GoldEngine(cfg)

    # The official paper cases fix all design variables through degenerate bounds.
    # Re-evaluating the lower bound therefore reproduces the exact case design
    # without introducing a second hidden design source.
    x = np.asarray(cfg.bounds.lower, dtype=float)
    _F, _G, _flows, raw_results = engine._evaluate_one_core(x)

    timestamps = pd.DatetimeIndex(pd.to_datetime(engine.profiles["timestamps"]))
    if len(timestamps) == 0:
        raise ValueError("[constant_thermflex_isolation] timestamps missing for time-series plot.")

    gas_chp_cap_kw_th = (
        float(cfg.district_gas_chp.installed_kw_el_max)
        * float(cfg.district_gas_chp.eta_th)
        / float(cfg.district_gas_chp.eta_el)
    )

    return {
        "override_path": str(override_path),
        "profile_start": str(cfg.run.profile_start),
        "profile_hours": int(cfg.run.profile_hours),
        "timestamps": timestamps,
        "dh_total_demand": np.asarray(raw_results["dh_total_demand"], dtype=float),
        "district_space_heat_demand": np.asarray(raw_results["district_space_heat_demand"], dtype=float),
        "district_space_heat_demand_ref": np.asarray(raw_results["district_space_heat_demand_ref"], dtype=float),
        "district_gas_boiler_generation": np.asarray(raw_results["district_gas_boiler_generation"], dtype=float),
        "district_gas_chp_thermal_generation": np.asarray(
            raw_results["district_gas_chp_thermal_generation"], dtype=float
        ),
        "district_heat_pump_generation": np.asarray(raw_results["district_heat_pump_generation"], dtype=float),
        "district_gas_boiler_cap_kw_th": float(cfg.district_gas_boiler.installed_kw_th_fixed),
        "district_gas_chp_cap_kw_th": float(gas_chp_cap_kw_th),
        "district_heat_pump_cap_kw_th": float(cfg.district_heat_pump.installed_kw_th_max),
        "constant_setpoint_c": float(cfg.heating_control.constant_setpoint_c),
        "constant_lower_bound_c": float(cfg.constraints.thermflex.constant_lower_bound_c),
        "constrain_upper_temperature": bool(cfg.constraints.thermflex.constrain_upper_temperature),
        "max_flex_duration_h": int(cfg.constraints.thermflex.max_flex_duration_h),
        "max_flex_events_per_day": int(cfg.constraints.thermflex.max_flex_events_per_day),
    }


def _write_timeseries_settings_summary(
    *,
    output_dir: Path,
    ref_series: dict[str, Any],
    flex_series: dict[str, Any],
) -> None:
    summary = {
        "slice": {
            "profile_start": ref_series["profile_start"],
            "profile_hours": ref_series["profile_hours"],
            "first_timestamp": str(ref_series["timestamps"][0]),
            "last_timestamp": str(ref_series["timestamps"][-1]),
        },
        "constant_no_thermflex": {
            "override_path": ref_series["override_path"],
            "constant_setpoint_c": ref_series["constant_setpoint_c"],
            "constant_lower_bound_c": ref_series["constant_lower_bound_c"],
            "constrain_upper_temperature": ref_series["constrain_upper_temperature"],
            "max_flex_duration_h": ref_series["max_flex_duration_h"],
            "max_flex_events_per_day": ref_series["max_flex_events_per_day"],
        },
        "constant_thermflex": {
            "override_path": flex_series["override_path"],
            "constant_setpoint_c": flex_series["constant_setpoint_c"],
            "constant_lower_bound_c": flex_series["constant_lower_bound_c"],
            "constrain_upper_temperature": flex_series["constrain_upper_temperature"],
            "max_flex_duration_h": flex_series["max_flex_duration_h"],
            "max_flex_events_per_day": flex_series["max_flex_events_per_day"],
        },
        "fixed_capacities_kw_th": {
            "district_gas_boiler": ref_series["district_gas_boiler_cap_kw_th"],
            "district_gas_chp_thermal_equivalent": ref_series["district_gas_chp_cap_kw_th"],
            "district_heat_pump": ref_series["district_heat_pump_cap_kw_th"],
        },
    }
    json_path = output_dir / "constant_thermflex_timeseries_settings.json"
    md_path = output_dir / "constant_thermflex_timeseries_settings.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    md_lines = [
        "# Constant Thermflex Time-Series Settings",
        "",
        f"- slice start: `{summary['slice']['profile_start']}`",
        f"- slice hours: `{summary['slice']['profile_hours']}`",
        f"- first timestamp: `{summary['slice']['first_timestamp']}`",
        f"- last timestamp: `{summary['slice']['last_timestamp']}`",
        "",
        "Constant no-thermflex:",
        f"- `constant_setpoint_c = {summary['constant_no_thermflex']['constant_setpoint_c']}`",
        f"- `constant_lower_bound_c = {summary['constant_no_thermflex']['constant_lower_bound_c']}`",
        f"- `constrain_upper_temperature = {summary['constant_no_thermflex']['constrain_upper_temperature']}`",
        f"- `max_flex_duration_h = {summary['constant_no_thermflex']['max_flex_duration_h']}`",
        f"- `max_flex_events_per_day = {summary['constant_no_thermflex']['max_flex_events_per_day']}`",
        "",
        "Constant thermflex:",
        f"- `constant_setpoint_c = {summary['constant_thermflex']['constant_setpoint_c']}`",
        f"- `constant_lower_bound_c = {summary['constant_thermflex']['constant_lower_bound_c']}`",
        f"- `constrain_upper_temperature = {summary['constant_thermflex']['constrain_upper_temperature']}`",
        f"- `max_flex_duration_h = {summary['constant_thermflex']['max_flex_duration_h']}`",
        f"- `max_flex_events_per_day = {summary['constant_thermflex']['max_flex_events_per_day']}`",
        "",
        "Fixed thermal capacities:",
        f"- `district_gas_boiler_cap_kw_th = {summary['fixed_capacities_kw_th']['district_gas_boiler']}`",
        f"- `district_gas_chp_thermal_equivalent_kw_th = {summary['fixed_capacities_kw_th']['district_gas_chp_thermal_equivalent']}`",
        f"- `district_heat_pump_cap_kw_th = {summary['fixed_capacities_kw_th']['district_heat_pump']}`",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")


def _save_timeseries_plot(
    *,
    output_dir: Path,
    ref_series: dict[str, Any],
    flex_series: dict[str, Any],
) -> None:
    ts = pd.DatetimeIndex(ref_series["timestamps"])
    hours = np.arange(len(ts), dtype=int)

    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=True)

    ax = axes[0, 0]
    ax.plot(hours, ref_series["district_space_heat_demand_ref"] / 1e3, color="#7f8c8d", linewidth=2.0, label="Reference")
    ax.plot(hours, flex_series["district_space_heat_demand"] / 1e3, color="#c0392b", linewidth=2.0, label="Thermflex actual")
    ax.fill_between(
        hours,
        ref_series["district_space_heat_demand_ref"] / 1e3,
        flex_series["district_space_heat_demand"] / 1e3,
        color="#c0392b",
        alpha=0.18,
        label="Shift delta",
    )
    ax.set_ylabel("MW thermal")
    ax.set_title("District Space-Heat Shift Over 24h")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()

    _plot_source_shift_panel(
        axes[0, 1],
        hours=hours,
        ref_values=ref_series["district_gas_boiler_generation"],
        flex_values=flex_series["district_gas_boiler_generation"],
        cap_value=ref_series["district_gas_boiler_cap_kw_th"],
        title="Gas Boiler Dispatch",
    )
    _plot_source_shift_panel(
        axes[1, 0],
        hours=hours,
        ref_values=ref_series["district_gas_chp_thermal_generation"],
        flex_values=flex_series["district_gas_chp_thermal_generation"],
        cap_value=ref_series["district_gas_chp_cap_kw_th"],
        title="Gas CHP Thermal Dispatch",
    )
    _plot_source_shift_panel(
        axes[1, 1],
        hours=hours,
        ref_values=ref_series["district_heat_pump_generation"],
        flex_values=flex_series["district_heat_pump_generation"],
        cap_value=ref_series["district_heat_pump_cap_kw_th"],
        title="District Heat Pump Dispatch",
    )

    tick_labels = [f"{int(h):02d}" for h in range(len(hours))]
    for ax in axes[1, :]:
        ax.set_xticks(hours)
        ax.set_xticklabels(tick_labels, rotation=0)
        ax.set_xlabel("Hour of slice")

    fig.tight_layout()
    fig.savefig(output_dir / "constant_thermflex_timeseries.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_source_shift_panel(
    ax: Any,
    *,
    hours: np.ndarray,
    ref_values: np.ndarray,
    flex_values: np.ndarray,
    cap_value: float,
    title: str,
) -> None:
    ax.plot(hours, np.asarray(ref_values, dtype=float) / 1e3, color="#7f8c8d", linewidth=2.0, label="No thermflex")
    ax.plot(hours, np.asarray(flex_values, dtype=float) / 1e3, color="#c0392b", linewidth=2.0, label="Thermflex")
    ax.axhline(float(cap_value) / 1e3, color="#2c3e50", linestyle="--", linewidth=1.2, label="Capacity cap")
    ax.set_ylabel("MW thermal")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
