from __future__ import annotations

"""Build Table 09 KPI outputs from one heating-season ThermFlex screen."""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESULT_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
TABLE_DIR = PROJECT_ROOT / "Documentation" / "Papers" / "thermflex_paper" / "tables"
DEFAULT_OUTPUT_MD = TABLE_DIR / "table_09_tradeoff_day_summary_upper_only_dur24.md"
DEFAULT_OUTPUT_CSV = TABLE_DIR / "table_09_heating_season_kpis_upper_only_dur24.csv"

REQUIRED_SCREEN_COLUMNS: tuple[str, ...] = (
    "date",
    "t_outdoor_mean_c",
    "dh_space_heat_total_kwh",
    "dispatch_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_flex",
    "co2_emissions_total_t_ref",
    "co2_emissions_total_t_flex",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_flex",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
)

NUMERIC_SCREEN_COLUMNS: tuple[str, ...] = (
    "t_outdoor_mean_c",
    "dh_space_heat_total_kwh",
    "dispatch_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_flex",
    "co2_emissions_total_t_ref",
    "co2_emissions_total_t_flex",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_flex",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
)

OPTIONAL_MAX_TIN_COLUMNS: tuple[str, ...] = (
    "max_t_in_above_setpoint_k",
    "max_tin_above_setpoint_k",
    "thermflex_max_t_in_above_setpoint_k",
)


@dataclass(frozen=True)
class Table09BuildResult:
    screen_csv: Path
    output_md: Path
    output_csv: Path
    selected_rows: int
    summary_rows: int


def build_table_09_heating_season_kpis(
    *,
    screen_csv: Path | str | None = None,
    output_md: Path | str | None = None,
    output_csv: Path | str | None = None,
) -> Table09BuildResult:
    """
    Build the Table 09 markdown and machine-readable season KPI summary.

    The caller must provide a real heating-season screen or rely on the latest
    `daily_thermflex_screen_*` result under the gold result root. The builder
    recalculates KPI deltas from explicit REF/FLEX columns instead of trusting
    stale derived columns that may have been copied from another screen.
    """

    screen_path = _resolve_screen_csv(screen_csv)
    output_md_path, output_csv_path = _resolve_output_paths(
        screen_path=screen_path,
        output_md=output_md,
        output_csv=output_csv,
        custom_screen_requested=screen_csv is not None,
    )
    screen = _load_screen(screen_path)
    selected = _select_tradeoff_days(screen)
    summary = _season_summary_rows(screen)

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_csv_path, index=False)
    output_md_path.write_text(
        _render_markdown(screen=screen, selected=selected, summary=summary),
        encoding="utf-8",
    )
    return Table09BuildResult(
        screen_csv=screen_path,
        output_md=output_md_path,
        output_csv=output_csv_path,
        selected_rows=int(len(selected)),
        summary_rows=int(len(summary)),
    )


def _resolve_screen_csv(screen_csv: Path | str | None) -> Path:
    if screen_csv is not None:
        path = Path(screen_csv).resolve()
        if not path.exists():
            raise FileNotFoundError(f"[table_09] screen CSV not found: {path}")
        return path
    if not RESULT_ROOT.exists():
        raise FileNotFoundError(f"[table_09] result root not found: {RESULT_ROOT}")
    candidates = sorted(
        RESULT_ROOT.glob("daily_thermflex_screen_*/heating_season_day_screen.csv"),
        key=lambda path: path.parent.name,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            "[table_09] no daily_thermflex_screen_* heating-season screen found under "
            f"{RESULT_ROOT}"
        )
    return candidates[0].resolve()


def _resolve_output_paths(
    *,
    screen_path: Path,
    output_md: Path | str | None,
    output_csv: Path | str | None,
    custom_screen_requested: bool,
) -> tuple[Path, Path]:
    if output_md is not None and output_csv is not None:
        return Path(output_md).resolve(), Path(output_csv).resolve()
    if custom_screen_requested:
        suffix = _screen_suffix(screen_path)
        default_md = TABLE_DIR / f"table_09_tradeoff_day_summary_{suffix}.md"
        default_csv = TABLE_DIR / f"table_09_heating_season_kpis_{suffix}.csv"
    else:
        default_md = DEFAULT_OUTPUT_MD
        default_csv = DEFAULT_OUTPUT_CSV
    return (
        Path(output_md).resolve() if output_md is not None else default_md.resolve(),
        Path(output_csv).resolve() if output_csv is not None else default_csv.resolve(),
    )


def _screen_suffix(screen_path: Path) -> str:
    raw = screen_path.parent.name.strip() or "custom_screen"
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw)
    return safe.strip("_") or "custom_screen"


def _load_screen(screen_path: Path) -> pd.DataFrame:
    df = pd.read_csv(screen_path)
    missing = sorted(set(REQUIRED_SCREEN_COLUMNS).difference(df.columns))
    if missing:
        raise KeyError("[table_09] screen CSV missing required columns: " + ", ".join(missing))
    loaded = df.copy()
    loaded["date"] = pd.to_datetime(loaded["date"], errors="raise")
    if loaded["date"].duplicated().any():
        duplicates = sorted(loaded.loc[loaded["date"].duplicated(), "date"].dt.strftime("%Y-%m-%d").unique())
        raise ValueError("[table_09] screen CSV contains duplicate dates: " + ", ".join(duplicates))
    for column in NUMERIC_SCREEN_COLUMNS:
        loaded[column] = pd.to_numeric(loaded[column], errors="raise")
        if not np.isfinite(loaded[column].to_numpy(dtype=float)).all():
            raise ValueError(f"[table_09] screen column contains non-finite values: {column}")
    loaded = loaded.sort_values("date").reset_index(drop=True)
    loaded["dispatch_operating_cost_eur_delta"] = (
        loaded["dispatch_operating_cost_eur_flex"] - loaded["dispatch_operating_cost_eur_ref"]
    )
    loaded["dispatch_operating_cost_pct_change"] = _pct_delta_series(
        loaded["dispatch_operating_cost_eur_flex"],
        loaded["dispatch_operating_cost_eur_ref"],
    )
    loaded["co2_emissions_total_t_delta"] = (
        loaded["co2_emissions_total_t_flex"] - loaded["co2_emissions_total_t_ref"]
    )
    loaded["co2_emissions_total_pct_change"] = _pct_delta_series(
        loaded["co2_emissions_total_t_flex"],
        loaded["co2_emissions_total_t_ref"],
    )
    loaded["district_gas_boiler_peak_kw_delta"] = (
        loaded["district_gas_boiler_peak_kw_flex"] - loaded["district_gas_boiler_peak_kw_ref"]
    )
    loaded["district_gas_boiler_peak_pct_change"] = _pct_delta_series(
        loaded["district_gas_boiler_peak_kw_flex"],
        loaded["district_gas_boiler_peak_kw_ref"],
    )
    loaded["district_gas_boiler_generation_kwh_delta"] = (
        loaded["district_gas_boiler_generation_kwh_flex"]
        - loaded["district_gas_boiler_generation_kwh_ref"]
    )
    loaded["district_gas_boiler_generation_pct_change"] = _pct_delta_series(
        loaded["district_gas_boiler_generation_kwh_flex"],
        loaded["district_gas_boiler_generation_kwh_ref"],
    )
    loaded["thermflex_rebound_over_shifted_pct"] = _pct_ratio_series(
        loaded["thermflex_rebound_kwh"],
        loaded["thermflex_shifted_space_heat_kwh"],
    )
    cost_gain = np.maximum(0.0, -loaded["dispatch_operating_cost_pct_change"].to_numpy(dtype=float))
    co2_gain = np.maximum(0.0, -loaded["co2_emissions_total_pct_change"].to_numpy(dtype=float))
    loaded["joint_savings_score"] = cost_gain + co2_gain
    return loaded


def _select_tradeoff_days(screen: pd.DataFrame) -> pd.DataFrame:
    selected_rows: list[pd.Series] = []
    used_dates: set[pd.Timestamp] = set()

    def take(label: str, reading: str, candidates: pd.DataFrame, *, limit: int) -> None:
        taken = 0
        for _, row in candidates.iterrows():
            day = pd.Timestamp(row["date"])
            if day in used_dates:
                continue
            item = row.copy()
            item["day_type"] = label
            item["reading"] = reading
            selected_rows.append(item)
            used_dates.add(day)
            taken += 1
            if taken >= limit:
                return

    take(
        "best joint savings day",
        "Clean top-savings day with strong joint cost and CO2 relief.",
        screen.sort_values("joint_savings_score", ascending=False),
        limit=1,
    )
    robust = screen.loc[
        (screen["dispatch_operating_cost_pct_change"] < 0.0)
        & (screen["co2_emissions_total_pct_change"] < 0.0)
    ].sort_values("joint_savings_score", ascending=False)
    take(
        "robust savings",
        "Cost and CO2 both improve under the active ThermFlex case.",
        robust,
        limit=4,
    )
    cold = screen.sort_values(
        ["dh_space_heat_total_kwh", "joint_savings_score"],
        ascending=[False, True],
    )
    take(
        "cold contrast",
        "High-heat winter contrast day where system value is comparatively weak.",
        cold,
        limit=1,
    )
    co2_tradeoff = screen.loc[
        (screen["co2_emissions_total_pct_change"] > 0.0)
        & (screen["dispatch_operating_cost_pct_change"] <= 0.0)
    ].sort_values(["co2_emissions_total_pct_change", "dispatch_operating_cost_pct_change"], ascending=[False, True])
    take(
        "late-season CO2 kink",
        "Cost does not worsen, but CO2 increases under flex.",
        co2_tradeoff,
        limit=3,
    )
    near_neutral = screen.loc[
        screen["joint_savings_score"].between(0.0, 0.3, inclusive="both")
    ].sort_values("thermflex_shifted_space_heat_kwh", ascending=False)
    take(
        "late-season near-neutral day",
        "Visible thermal movement with almost no net system value.",
        near_neutral,
        limit=1,
    )
    if not selected_rows:
        raise ValueError("[table_09] no rows available for tradeoff-day selection.")
    selected = pd.DataFrame(selected_rows).sort_values("date").reset_index(drop=True)
    return selected


def _season_summary_rows(screen: pd.DataFrame) -> pd.DataFrame:
    rows = [_summarize_period(screen, scope="heating_season_total")]
    rows.extend(_rolling_best_windows(screen, window_days=7))
    return pd.DataFrame(rows)


def _rolling_best_windows(screen: pd.DataFrame, *, window_days: int) -> list[dict[str, object]]:
    if len(screen) < window_days:
        return []
    ordered = screen.sort_values("date").reset_index(drop=True)
    candidates: list[tuple[str, pd.DataFrame, float]] = []
    for start in range(0, len(ordered) - window_days + 1):
        window = ordered.iloc[start : start + window_days].copy()
        candidates.append(("best_7d_cost", window, float(window["dispatch_operating_cost_eur_delta"].sum())))
        candidates.append(("best_7d_co2", window, float(window["co2_emissions_total_t_delta"].sum())))
        candidates.append(
            (
                "best_7d_boiler_energy",
                window,
                float(window["district_gas_boiler_generation_kwh_delta"].sum()),
            )
        )
    rows: list[dict[str, object]] = []
    for scope in ("best_7d_cost", "best_7d_co2", "best_7d_boiler_energy"):
        scoped = [item for item in candidates if item[0] == scope]
        _, window, _ = min(scoped, key=lambda item: item[2])
        rows.append(_summarize_period(window, scope=scope))
    return rows


def _summarize_period(frame: pd.DataFrame, *, scope: str) -> dict[str, object]:
    cost_ref = float(frame["dispatch_operating_cost_eur_ref"].sum())
    cost_flex = float(frame["dispatch_operating_cost_eur_flex"].sum())
    co2_ref = float(frame["co2_emissions_total_t_ref"].sum())
    co2_flex = float(frame["co2_emissions_total_t_flex"].sum())
    boiler_ref = float(frame["district_gas_boiler_generation_kwh_ref"].sum())
    boiler_flex = float(frame["district_gas_boiler_generation_kwh_flex"].sum())
    peak_ref = float(frame["district_gas_boiler_peak_kw_ref"].max())
    peak_flex = float(frame["district_gas_boiler_peak_kw_flex"].max())
    shifted = float(frame["thermflex_shifted_space_heat_kwh"].sum())
    rebound = float(frame["thermflex_rebound_kwh"].sum())
    return {
        "scope": scope,
        "start_date": pd.Timestamp(frame["date"].min()).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(frame["date"].max()).strftime("%Y-%m-%d"),
        "day_count": int(len(frame)),
        "dispatch_operating_cost_eur_ref": cost_ref,
        "dispatch_operating_cost_eur_flex": cost_flex,
        "dispatch_operating_cost_eur_delta": cost_flex - cost_ref,
        "dispatch_operating_cost_pct_change": _pct_delta_scalar(cost_flex, cost_ref),
        "co2_emissions_total_t_ref": co2_ref,
        "co2_emissions_total_t_flex": co2_flex,
        "co2_emissions_total_t_delta": co2_flex - co2_ref,
        "co2_emissions_total_pct_change": _pct_delta_scalar(co2_flex, co2_ref),
        "district_gas_boiler_generation_kwh_ref": boiler_ref,
        "district_gas_boiler_generation_kwh_flex": boiler_flex,
        "district_gas_boiler_generation_kwh_delta": boiler_flex - boiler_ref,
        "district_gas_boiler_generation_pct_change": _pct_delta_scalar(boiler_flex, boiler_ref),
        "district_gas_boiler_peak_kw_ref": peak_ref,
        "district_gas_boiler_peak_kw_flex": peak_flex,
        "district_gas_boiler_peak_kw_delta": peak_flex - peak_ref,
        "district_gas_boiler_peak_pct_change": _pct_delta_scalar(peak_flex, peak_ref),
        "thermflex_shifted_space_heat_kwh": shifted,
        "thermflex_rebound_kwh": rebound,
        "thermflex_rebound_over_shifted_pct": _pct_delta_scalar(rebound, shifted, ratio=True),
    }


def _render_markdown(*, screen: pd.DataFrame, selected: pd.DataFrame, summary: pd.DataFrame) -> str:
    season = summary.loc[summary["scope"] == "heating_season_total"].iloc[0]
    lines = [
        "| Date | Day type | Mean outdoor temperature [degC] | Cost change [%] | CO2 change [%] | Boiler energy change [%] | Boiler peak change [%] | Shifted heat [MWh] | Rebound heat [MWh] | Rebound / shifted [%] | Max T_in above setpoint [K] | Reading |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for _, row in selected.iterrows():
        lines.append(
            "| "
            f"{pd.Timestamp(row['date']).strftime('%Y-%m-%d')} | "
            f"{row['day_type']} | "
            f"{_fmt_number(row['t_outdoor_mean_c'], digits=1)} | "
            f"{_fmt_number(row['dispatch_operating_cost_pct_change'], digits=2, signed=True)} | "
            f"{_fmt_number(row['co2_emissions_total_pct_change'], digits=2, signed=True)} | "
            f"{_fmt_number(row['district_gas_boiler_generation_pct_change'], digits=2, signed=True)} | "
            f"{_fmt_number(row['district_gas_boiler_peak_pct_change'], digits=2, signed=True)} | "
            f"{_fmt_number(float(row['thermflex_shifted_space_heat_kwh']) / 1e3, digits=1)} | "
            f"{_fmt_number(float(row['thermflex_rebound_kwh']) / 1e3, digits=1)} | "
            f"{_fmt_number(row['thermflex_rebound_over_shifted_pct'], digits=1)} | "
            f"{_fmt_optional_max_tin(row)} | "
            f"{row['reading']} |"
        )
    lines.extend(
        [
            "",
            "Heating-season aggregate:",
            f"- Days: `{int(season['day_count'])}` (`{season['start_date']}` to `{season['end_date']}`).",
            f"- Cost change: `{_fmt_number(season['dispatch_operating_cost_eur_delta'], digits=2, signed=True)}` EUR / `{_fmt_number(season['dispatch_operating_cost_pct_change'], digits=2, signed=True)}`%.",
            f"- CO2 change: `{_fmt_number(season['co2_emissions_total_t_delta'], digits=2, signed=True)}` t / `{_fmt_number(season['co2_emissions_total_pct_change'], digits=2, signed=True)}`%.",
            f"- Boiler energy change: `{_fmt_number(float(season['district_gas_boiler_generation_kwh_delta']) / 1e6, digits=2, signed=True)}` GWh / `{_fmt_number(season['district_gas_boiler_generation_pct_change'], digits=2, signed=True)}`%.",
            f"- Boiler peak change: `{_fmt_number(season['district_gas_boiler_peak_pct_change'], digits=2, signed=True)}`%.",
            f"- Shifted heat: `{_fmt_number(float(season['thermflex_shifted_space_heat_kwh']) / 1e6, digits=2)}` GWh.",
            f"- Rebound heat: `{_fmt_number(float(season['thermflex_rebound_kwh']) / 1e6, digits=2)}` GWh.",
            "",
            "Active case:",
            *[f"- `{value}`" for value in _active_case_lines(screen)],
            "",
            "Interpretation:",
            "- The table is generated directly from the supplied heating-season screen.",
            "- The companion CSV stores aggregate season and rolling-window KPIs for machine checks.",
        ]
    )
    return "\n".join(lines) + "\n"


def _active_case_lines(screen: pd.DataFrame) -> list[str]:
    values: list[str] = []
    if "flex_case_label" in screen.columns:
        labels = sorted(screen["flex_case_label"].dropna().astype(str).unique().tolist())
        values.extend(labels)
    if "flex_override_name" in screen.columns:
        overrides = sorted(screen["flex_override_name"].dropna().astype(str).unique().tolist())
        values.extend(overrides)
    return values or ["unspecified"]


def _fmt_optional_max_tin(row: pd.Series) -> str:
    for column in OPTIONAL_MAX_TIN_COLUMNS:
        if column not in row.index or pd.isna(row[column]):
            continue
        return _fmt_number(row[column], digits=2)
    return "n/a"


def _pct_delta_series(flex: pd.Series, ref: pd.Series) -> pd.Series:
    ref_arr = ref.to_numpy(dtype=float)
    flex_arr = flex.to_numpy(dtype=float)
    out = np.full_like(ref_arr, np.nan, dtype=float)
    mask = np.abs(ref_arr) > 1e-12
    out[mask] = 100.0 * (flex_arr[mask] - ref_arr[mask]) / ref_arr[mask]
    return pd.Series(out, index=ref.index)


def _pct_ratio_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom_arr = denominator.to_numpy(dtype=float)
    numerator_arr = numerator.to_numpy(dtype=float)
    out = np.full_like(denom_arr, np.nan, dtype=float)
    mask = np.abs(denom_arr) > 1e-12
    out[mask] = 100.0 * numerator_arr[mask] / denom_arr[mask]
    return pd.Series(out, index=denominator.index)


def _pct_delta_scalar(flex: float, ref: float, *, ratio: bool = False) -> float:
    if abs(ref) <= 1e-12:
        return float("nan")
    if ratio:
        return float(100.0 * flex / ref)
    return float(100.0 * (flex - ref) / ref)


def _fmt_number(value: object, *, digits: int, signed: bool = False) -> str:
    numeric = float(value)
    if not np.isfinite(numeric):
        return "n/a"
    sign = "+" if signed else ""
    return f"{numeric:{sign}.{digits}f}"


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-csv", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = _parse_args(argv)
    result = build_table_09_heating_season_kpis(
        screen_csv=args.screen_csv,
        output_md=args.output_md,
        output_csv=args.output_csv,
    )
    print(result.output_md)
    print(result.output_csv)


if __name__ == "__main__":
    main()
