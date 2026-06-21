from __future__ import annotations

"""Build the ThermFlex paper Table 09 from a heating-season day screen."""

import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESULT_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
TABLE_DIR = PROJECT_ROOT / "Documentation" / "Papers" / "thermflex_paper" / "tables"
DEFAULT_TABLE_MD = TABLE_DIR / "table_09_tradeoff_day_summary_upper_only_dur24.md"
DEFAULT_TABLE_CSV = TABLE_DIR / "table_09_tradeoff_day_summary_upper_only_dur24.csv"

REQUIRED_SCREEN_COLUMNS: Tuple[str, ...] = (
    "date",
    "t_outdoor_mean_c",
    "dh_space_heat_total_kwh",
    "dispatch_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_flex",
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_t_ref",
    "co2_emissions_total_t_flex",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_peak_pct_change",
    "district_gas_boiler_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_flex",
    "district_gas_boiler_generation_pct_change",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_rebound_over_shifted_pct",
)

OPTIONAL_MAX_T_COLUMNS: Tuple[str, ...] = (
    "max_t_in_above_setpoint_k",
    "max_tin_above_setpoint_k",
    "cohort_max_delta_t_in_k",
)


def build_table_09_heating_season_kpis(
    *,
    screen_csv: Path | str | None = None,
    output_md: Path | str | None = None,
    output_csv: Path | str | None = None,
) -> Tuple[Path, Path]:
    """Write Table 09 markdown and CSV outputs from one explicit day screen.

    The input screen is the single source of truth for all Table 09 values.
    Missing KPI columns fail immediately so a surrogate-generated screen cannot
    be accepted with partially blank or zero-filled paper metrics.
    """

    screen_path = Path(screen_csv).resolve() if screen_csv is not None else _resolve_latest_screen_csv()
    if not screen_path.exists():
        raise FileNotFoundError(f"[table_09] screen CSV not found: {screen_path}")
    md_path, csv_path = _resolve_output_paths(
        screen_path=screen_path,
        output_md=output_md,
        output_csv=output_csv,
    )
    screen = _load_screen(screen_path)
    selected = _select_table_days(screen)
    selected.to_csv(csv_path, index=False)
    md_path.write_text(
        _render_markdown(screen=screen, selected=selected, screen_path=screen_path),
        encoding="utf-8",
    )
    return md_path, csv_path


def _resolve_latest_screen_csv() -> Path:
    if not RESULT_ROOT.exists():
        raise FileNotFoundError(f"[table_09] result root not found: {RESULT_ROOT}")
    candidates = [
        path / "heating_season_day_screen.csv"
        for path in RESULT_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("daily_thermflex_screen_")
    ]
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        raise FileNotFoundError("[table_09] no daily_thermflex_screen_* heating-season screen found.")
    candidates.sort(key=lambda path: path.parent.name, reverse=True)
    return candidates[0].resolve()


def _resolve_output_paths(
    *,
    screen_path: Path,
    output_md: Path | str | None,
    output_csv: Path | str | None,
) -> Tuple[Path, Path]:
    if output_md is None and output_csv is None:
        return DEFAULT_TABLE_MD.resolve(), DEFAULT_TABLE_CSV.resolve()
    if output_md is None:
        output_md = TABLE_DIR / f"table_09_tradeoff_day_summary_{screen_path.parent.name}.md"
    if output_csv is None:
        output_csv = TABLE_DIR / f"table_09_tradeoff_day_summary_{screen_path.parent.name}.csv"
    md_path = Path(output_md).resolve()
    csv_path = Path(output_csv).resolve()
    md_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    return md_path, csv_path


def _load_screen(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_SCREEN_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError("[table_09] screen CSV missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("[table_09] screen CSV is empty.")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="raise")
    numeric_columns = [column for column in REQUIRED_SCREEN_COLUMNS if column != "date"]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="raise")
    for column in OPTIONAL_MAX_T_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="raise")
    if "joint_savings_score" not in out.columns:
        cost_gain = (-out["dispatch_operating_cost_pct_change"]).clip(lower=0.0)
        co2_gain = (-out["co2_emissions_total_pct_change"]).clip(lower=0.0)
        out["joint_savings_score"] = cost_gain + co2_gain
    else:
        out["joint_savings_score"] = pd.to_numeric(out["joint_savings_score"], errors="raise")
    return out.sort_values("date").reset_index(drop=True)


def _select_table_days(screen: pd.DataFrame) -> pd.DataFrame:
    selected: List[Dict[str, Any]] = []
    used_dates: set[pd.Timestamp] = set()

    def add_rows(label: str, rows: pd.DataFrame, limit: int) -> None:
        for _, row in rows.iterrows():
            date = pd.Timestamp(row["date"])
            if date in used_dates:
                continue
            selected.append(_selected_row(row=row, day_type=label))
            used_dates.add(date)
            if sum(1 for item in selected if item["day_type"] == label) >= limit:
                return

    cold = screen.sort_values(
        ["dh_space_heat_total_kwh", "dispatch_operating_cost_pct_change"],
        ascending=[False, True],
    )
    add_rows("cold contrast", cold, 1)

    joint = screen.sort_values("joint_savings_score", ascending=False)
    add_rows("best joint savings day", joint, 1)

    robust = screen.loc[
        (screen["dispatch_operating_cost_pct_change"] < 0.0)
        & (screen["co2_emissions_total_pct_change"] < 0.0)
    ].sort_values("joint_savings_score", ascending=False)
    add_rows("robust savings", robust, 4)

    peak_kink = robust.loc[robust["district_gas_boiler_peak_pct_change"] > 0.0].sort_values(
        "district_gas_boiler_peak_pct_change",
        ascending=False,
    )
    add_rows("robust savings, peak kink", peak_kink, 2)

    late_co2 = screen.loc[
        (screen["date"].dt.month >= 3)
        & (screen["co2_emissions_total_pct_change"] > 0.0)
    ].sort_values("co2_emissions_total_pct_change", ascending=False)
    add_rows("late-season CO2 kink", late_co2, 2)

    near_neutral = screen.loc[
        (screen["date"].dt.month >= 3)
        & (screen["dispatch_operating_cost_pct_change"].abs() <= 0.1)
    ].assign(_abs_cost=lambda df: df["dispatch_operating_cost_pct_change"].abs())
    near_neutral = near_neutral.sort_values(["_abs_cost", "date"])
    add_rows("late-season near-neutral day", near_neutral, 1)

    if len(selected) < min(10, len(screen)):
        add_rows("additional high-savings day", joint, min(10, len(screen)) - len(selected))

    if not selected:
        raise ValueError("[table_09] no selectable days found in screen.")
    out = pd.DataFrame(selected)
    return out.sort_values("date").reset_index(drop=True)


def _selected_row(*, row: pd.Series, day_type: str) -> Dict[str, Any]:
    selected = {
        "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
        "day_type": day_type,
        "t_outdoor_mean_c": float(row["t_outdoor_mean_c"]),
        "dispatch_operating_cost_pct_change": float(row["dispatch_operating_cost_pct_change"]),
        "co2_emissions_total_pct_change": float(row["co2_emissions_total_pct_change"]),
        "district_gas_boiler_generation_pct_change": float(row["district_gas_boiler_generation_pct_change"]),
        "district_gas_boiler_peak_pct_change": float(row["district_gas_boiler_peak_pct_change"]),
        "thermflex_shifted_space_heat_mwh": float(row["thermflex_shifted_space_heat_kwh"]) / 1e3,
        "thermflex_rebound_mwh": float(row["thermflex_rebound_kwh"]) / 1e3,
        "thermflex_rebound_over_shifted_pct": _maybe_float(row["thermflex_rebound_over_shifted_pct"]),
        "max_t_in_above_setpoint_k": _resolve_optional_max_t(row),
        "reading": _reading_for_day_type(day_type),
    }
    return selected


def _resolve_optional_max_t(row: pd.Series) -> float | None:
    for column in OPTIONAL_MAX_T_COLUMNS:
        if column in row.index and pd.notna(row[column]):
            return float(row[column])
    return None


def _maybe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _reading_for_day_type(day_type: str) -> str:
    readings = {
        "cold contrast": "Cold high-load day used to separate demand size from flexibility value.",
        "best joint savings day": "Strongest combined cost and CO2 saving day in the selected screen.",
        "robust savings": "Cost and CO2 savings are both positive in the flex case.",
        "robust savings, peak kink": "Joint savings remain positive although another hour lifts the boiler peak.",
        "late-season CO2 kink": "Late-season flexibility worsens CO2 despite visible heat shifting.",
        "late-season near-neutral day": "Thermal movement is visible while headline system KPIs are almost flat.",
        "additional high-savings day": "Additional high-ranking day by joint cost and CO2 savings.",
    }
    return readings.get(day_type, "")


def _render_markdown(*, screen: pd.DataFrame, selected: pd.DataFrame, screen_path: Path) -> str:
    lines = [
        "| Date | Day type | Mean outdoor temperature [degC] | Cost change [%] | CO2 change [%] | Boiler energy change [%] | Boiler peak change [%] | Shifted heat [MWh] | Rebound heat [MWh] | Rebound / shifted [%] | Max T_in above setpoint [K] | Reading |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in selected.itertuples(index=False):
        lines.append(
            "| "
            f"{row.date} | "
            f"{row.day_type} | "
            f"{float(row.t_outdoor_mean_c):.1f} | "
            f"{_fmt_signed(row.dispatch_operating_cost_pct_change)} | "
            f"{_fmt_signed(row.co2_emissions_total_pct_change)} | "
            f"{_fmt_signed(row.district_gas_boiler_generation_pct_change)} | "
            f"{_fmt_signed(row.district_gas_boiler_peak_pct_change)} | "
            f"{float(row.thermflex_shifted_space_heat_mwh):.1f} | "
            f"{float(row.thermflex_rebound_mwh):.1f} | "
            f"{_fmt_optional(row.thermflex_rebound_over_shifted_pct)} | "
            f"{_fmt_optional(row.max_t_in_above_setpoint_k)} | "
            f"{row.reading} |"
        )

    season = _season_summary(screen)
    case_label = _first_text(screen, "flex_case_label")
    override_name = _first_text(screen, "flex_override_name")
    lines.extend(
        [
            "",
            "Season summary:",
            f"- Screen source: `{screen_path}`",
            f"- Heating days screened: `{season['n_days']}`",
            f"- Cost change: `{_fmt_signed(season['cost_pct_change'])} %`",
            f"- CO2 change: `{_fmt_signed(season['co2_pct_change'])} %`",
            f"- Boiler energy change: `{_fmt_signed(season['boiler_energy_pct_change'])} %`",
            f"- Boiler peak change: `{_fmt_signed(season['boiler_peak_pct_change'])} %`",
            f"- Shifted heat: `{season['shifted_heat_mwh']:.1f} MWh`",
            f"- Rebound heat: `{season['rebound_heat_mwh']:.1f} MWh`",
            "",
            "Active case:",
            f"- `{case_label or 'unknown'}`",
            f"- override `{override_name or 'unknown'}`",
            "",
            "Interpretation:",
            "- The table is rebuilt directly from the supplied heating-season day screen.",
            "- Required paper KPI columns are validated before any markdown or CSV output is written.",
        ]
    )
    return "\n".join(lines) + "\n"


def _season_summary(screen: pd.DataFrame) -> Dict[str, float | int]:
    cost_ref = float(screen["dispatch_operating_cost_eur_ref"].sum())
    cost_flex = float(screen["dispatch_operating_cost_eur_flex"].sum())
    co2_ref = float(screen["co2_emissions_total_t_ref"].sum())
    co2_flex = float(screen["co2_emissions_total_t_flex"].sum())
    boiler_ref = float(screen["district_gas_boiler_generation_kwh_ref"].sum())
    boiler_flex = float(screen["district_gas_boiler_generation_kwh_flex"].sum())
    peak_ref = float(screen["district_gas_boiler_peak_kw_ref"].max())
    peak_flex = float(screen["district_gas_boiler_peak_kw_flex"].max())
    return {
        "n_days": int(len(screen)),
        "cost_pct_change": _pct_delta(cost_flex, cost_ref),
        "co2_pct_change": _pct_delta(co2_flex, co2_ref),
        "boiler_energy_pct_change": _pct_delta(boiler_flex, boiler_ref),
        "boiler_peak_pct_change": _pct_delta(peak_flex, peak_ref),
        "shifted_heat_mwh": float(screen["thermflex_shifted_space_heat_kwh"].sum()) / 1e3,
        "rebound_heat_mwh": float(screen["thermflex_rebound_kwh"].sum()) / 1e3,
    }


def _pct_delta(flex_value: float, ref_value: float) -> float:
    if abs(float(ref_value)) <= 1e-12:
        raise ZeroDivisionError("[table_09] cannot compute percentage change against a zero reference value.")
    return float(100.0 * (float(flex_value) - float(ref_value)) / float(ref_value))


def _first_text(screen: pd.DataFrame, column: str) -> str | None:
    if column not in screen.columns:
        return None
    values = [str(value).strip() for value in screen[column].dropna().tolist()]
    return values[0] if values and values[0] else None


def _fmt_signed(value: float) -> str:
    numeric = float(value)
    return f"{numeric:+.2f}" if numeric > 0.0 else f"{numeric:.2f}"


def _fmt_optional(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ThermFlex paper Table 09 from a day-screen CSV.")
    parser.add_argument("--screen-csv", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-csv", default="")
    args = parser.parse_args()
    md_path, csv_path = build_table_09_heating_season_kpis(
        screen_csv=args.screen_csv or None,
        output_md=args.output_md or None,
        output_csv=args.output_csv or None,
    )
    print(f"[table_09] wrote {md_path}")
    print(f"[table_09] wrote {csv_path}")


if __name__ == "__main__":
    main()
