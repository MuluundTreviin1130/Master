from __future__ import annotations

"""Build a compact mechanism bundle from the active Vienna `upper_only dur24` path.

The bundle is intentionally narrow:
- use one explicit heating-season daily screen as SSOT for system KPIs,
- classify top-savings, trade-off and cold-contrast days from that screen,
- relate those outcomes to the yearly solar proxy without extra model guesses,
- replay a small selected-day subset to extract cohort-level flex use.

This keeps the current paper work honest:
- no hidden optimizer layer,
- no second KPI source,
- no manual day picking outside the explicit screen outputs.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT_STR = str(PROJECT_ROOT.resolve())
if PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_STR)

from Optimization.framework.engines.Gold.gold_engine import GoldEngine
from Optimization.run.analysis.build_constant_thermflex_cohort_utilization import _build_case_tables
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context
from Settings import get_settings

RESULT_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
OVERRIDE_DIR = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
FLEX_OVERRIDE = (
    OVERRIDE_DIR
    / "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json"
)
SETPOINT_C = 22.5
SELECTED_DAY_ORDER = (
    "best_joint_savings",
    "robust_savings",
    "cold_contrast",
    "co2_tradeoff",
    "late_season_near_neutral",
)


@dataclass(frozen=True)
class SelectedDay:
    """Explicit selected-day descriptor for downstream bundle exports."""

    label: str
    date: str
    rationale: str


def build_vienna_constant_thermflex_mechanism_bundle(
    *,
    screen_dir: Path | None = None,
) -> Path:
    """Build one explicit bundle from the latest active `dur24` daily screen."""

    screen_dir = Path(screen_dir).resolve() if screen_dir is not None else _resolve_latest_screen_dir()
    screen_csv = screen_dir / "heating_season_day_screen.csv"
    if not screen_csv.exists():
        raise FileNotFoundError(
            "[build_vienna_constant_thermflex_mechanism_bundle] screen CSV not found: "
            f"{screen_csv}"
        )

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RESULT_ROOT / f"paper_mechanism_bundle_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    screen_df = pd.read_csv(screen_csv)
    if screen_df.empty:
        raise ValueError("[build_vienna_constant_thermflex_mechanism_bundle] screen CSV is empty.")
    screen_df["date"] = screen_df["date"].astype(str)

    context = load_vienna_dh_thermflex_full_year_context()
    daily_context = _build_daily_context_table(context)
    merged_df = screen_df.merge(daily_context, on="date", how="left", validate="one_to_one")
    missing_context = merged_df["solargains_proxy_sum_ctx"].isna()
    if bool(missing_context.any()):
        raise ValueError(
            "[build_vienna_constant_thermflex_mechanism_bundle] missing daily context rows for dates: "
            + ", ".join(merged_df.loc[missing_context, "date"].astype(str).tolist())
        )

    selected_days = _select_days(merged_df)
    selected_df = _materialize_selected_days(merged_df, selected_days)
    solar_bins_df = _build_solar_bin_summary(merged_df)
    cohort_df = _build_selected_day_cohort_summary(selected_days)

    merged_df.to_csv(output_dir / "heating_season_screen_joined.csv", index=False)
    selected_df.to_csv(output_dir / "selected_days.csv", index=False)
    solar_bins_df.to_csv(output_dir / "solar_bin_summary.csv", index=False)
    cohort_df.to_csv(output_dir / "selected_day_cohort_summary.csv", index=False)

    payload = {
        "screen_dir": str(screen_dir),
        "screen_csv": str(screen_csv),
        "selected_days": [day.__dict__ for day in selected_days],
        "flex_override": str(FLEX_OVERRIDE),
    }
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown_summary(
        output_dir=output_dir,
        selected_df=selected_df,
        solar_bins_df=solar_bins_df,
        cohort_df=cohort_df,
    )
    return output_dir


def _resolve_latest_screen_dir() -> Path:
    matches = [
        path
        for path in RESULT_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("daily_thermflex_screen_dur24_")
    ]
    if not matches:
        raise FileNotFoundError(
            "[build_vienna_constant_thermflex_mechanism_bundle] no `daily_thermflex_screen_dur24_*` result dir found."
        )
    matches.sort(key=lambda path: path.name, reverse=True)
    return matches[0]


def _build_daily_context_table(context: Any) -> pd.DataFrame:
    hourly = context.hourly_system_df.copy()
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"])
    hourly["date"] = hourly["timestamp"].dt.strftime("%Y-%m-%d")
    daily = (
        hourly.groupby("date", as_index=False)
        .agg(
            irradiance_proxy_sum_ctx=("irradiance_proxy", "sum"),
            solargains_proxy_sum_ctx=("solargains_proxy", "sum"),
            t_outdoor_mean_c_ctx=("t_outdoor_c", "mean"),
            dh_space_heat_total_kwh_ctx=("dh_space_heat_total_kwh", "sum"),
        )
    )
    return daily


def _select_days(screen_df: pd.DataFrame) -> list[SelectedDay]:
    rows: list[SelectedDay] = []
    used_dates: set[str] = set()

    def pick(label: str, rationale: str, candidates: pd.DataFrame) -> None:
        for row in candidates.itertuples(index=False):
            day_date = str(row.date)
            if day_date in used_dates:
                continue
            used_dates.add(day_date)
            rows.append(SelectedDay(label=label, date=day_date, rationale=rationale))
            return
        raise ValueError(
            "[build_vienna_constant_thermflex_mechanism_bundle] no unique candidate available for "
            f"{label}."
        )

    best_joint = screen_df.sort_values("joint_savings_score", ascending=False)
    pick(
        "best_joint_savings",
        "Highest joint cost+CO2 savings score on the active dur24 upper-only path.",
        best_joint,
    )
    robust_savings_pool = screen_df[
        (screen_df["dispatch_operating_cost_pct_change"] < -1.0)
        & (screen_df["co2_emissions_total_pct_change"] < -1.0)
        & (screen_df["district_gas_boiler_peak_pct_change"] <= 0.0)
    ].sort_values("joint_savings_score", ascending=False)
    pick(
        "robust_savings",
        "Strong savings day without a boiler-peak penalty.",
        robust_savings_pool,
    )
    cold_contrast_pool = screen_df.sort_values(
        ["dh_space_heat_total_kwh", "joint_savings_score"],
        ascending=[False, True],
    )
    pick(
        "cold_contrast",
        "High-heat winter contrast day with weak overall thermflex value.",
        cold_contrast_pool,
    )
    co2_tradeoff_pool = screen_df[
        (screen_df["co2_emissions_total_pct_change"] > 0.0)
        & (screen_df["dispatch_operating_cost_pct_change"] <= 0.0)
    ].sort_values(
        ["co2_emissions_total_pct_change", "dispatch_operating_cost_pct_change"],
        ascending=[False, True],
    )
    pick(
        "co2_tradeoff",
        "Day where cost does not worsen but CO2 increases under flex.",
        co2_tradeoff_pool,
    )
    near_neutral_pool = screen_df[
        screen_df["joint_savings_score"].between(0.0, 0.3, inclusive="both")
    ].sort_values(
        ["solargains_proxy_sum_ctx", "dh_space_heat_total_kwh"],
        ascending=[False, False],
    )
    pick(
        "late_season_near_neutral",
        "Visible thermal activity with almost no system-level value.",
        near_neutral_pool,
    )
    return rows


def _materialize_selected_days(screen_df: pd.DataFrame, selected_days: list[SelectedDay]) -> pd.DataFrame:
    order = {label: idx for idx, label in enumerate(SELECTED_DAY_ORDER)}
    rows: list[dict[str, Any]] = []
    for item in selected_days:
        match = screen_df.loc[screen_df["date"] == item.date]
        if len(match) != 1:
            raise ValueError(
                "[build_vienna_constant_thermflex_mechanism_bundle] expected one screen row for date "
                f"{item.date}, found {len(match)}."
            )
        row = match.iloc[0].to_dict()
        row["selection_label"] = item.label
        row["selection_rationale"] = item.rationale
        rows.append(row)
    selected_df = pd.DataFrame(rows)
    selected_df["selection_order"] = selected_df["selection_label"].map(order)
    selected_df = selected_df.sort_values("selection_order").reset_index(drop=True)
    return selected_df


def _build_solar_bin_summary(screen_df: pd.DataFrame) -> pd.DataFrame:
    working = screen_df.copy()
    try:
        working["solar_bin"] = pd.qcut(
            working["solargains_proxy_sum_ctx"],
            q=3,
            labels=["low solar", "mid solar", "high solar"],
            duplicates="drop",
        )
    except ValueError as exc:
        raise ValueError(
            "[build_vienna_constant_thermflex_mechanism_bundle] unable to build solar quantile bins."
        ) from exc
    summary = (
        working.groupby("solar_bin", observed=False)
        .agg(
            day_count=("date", "count"),
            mean_solargains_proxy_sum=("solargains_proxy_sum_ctx", "mean"),
            mean_shifted_heat_mwh=("thermflex_shifted_space_heat_kwh", lambda s: float(s.mean()) / 1e3),
            mean_rebound_over_shifted_pct=("thermflex_rebound_over_shifted_pct", "mean"),
            mean_cost_change_pct=("dispatch_operating_cost_pct_change", "mean"),
            mean_co2_change_pct=("co2_emissions_total_pct_change", "mean"),
            mean_joint_savings_score=("joint_savings_score", "mean"),
        )
        .reset_index()
    )
    summary["solar_bin"] = summary["solar_bin"].astype(str)
    return summary


def _build_selected_day_cohort_summary(selected_days: list[SelectedDay]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in selected_days:
        raw_results, run_dir, day_settings = _replay_day_slice(
            override_path=FLEX_OVERRIDE,
            day_date=item.date,
        )
        _hourly_rows, summary_rows = _build_case_tables(
            case_label=f"upper_only_dur24_{item.date}",
            run_dir=run_dir,
            settings=day_settings,
            raw_results=raw_results,
        )
        day_df = pd.DataFrame(summary_rows)
        residential_df = day_df.loc[day_df["cohort_key"].astype(str).str.startswith("residential_")].copy()
        residential_df["date"] = item.date
        residential_df["selection_label"] = item.label
        residential_df["selection_rationale"] = item.rationale
        residential_df["cohort_shifted_wh_per_m2"] = (
            1000.0 * residential_df["cohort_shifted_space_heat_kwh"] / residential_df["cohort_floor_area_m2"]
        )
        residential_df["cohort_rebound_wh_per_m2"] = (
            1000.0 * residential_df["cohort_rebound_kwh"] / residential_df["cohort_floor_area_m2"]
        )
        residential_df["cohort_preheat_wh_per_m2"] = (
            1000.0
            * residential_df["cohort_preheat_extra_realized_kwh"]
            / residential_df["cohort_floor_area_m2"]
        )
        residential_df["cohort_cutback_wh_per_m2"] = (
            1000.0
            * residential_df["cohort_cutback_shed_realized_kwh"]
            / residential_df["cohort_floor_area_m2"]
        )
        residential_df["cohort_max_delta_t_in_k"] = (
            residential_df["cohort_t_in_weighted_max_c"] - SETPOINT_C
        )
        rows.extend(residential_df.to_dict(orient="records"))
    if not rows:
        raise ValueError("[build_vienna_constant_thermflex_mechanism_bundle] no cohort rows produced.")
    return pd.DataFrame(rows)


def _replay_day_slice(*, override_path: Path, day_date: str) -> tuple[dict[str, Any], Path, Any]:
    overrides = json.loads(Path(override_path).read_text(encoding="utf-8-sig"))
    overrides["run"]["profile_start"] = f"{day_date} 00:00:00"
    overrides["run"]["profile_hours"] = 24
    overrides["run"]["tag"] = f"{Path(override_path).stem}_{day_date.replace('-', '')}_mechanism"
    day_settings = get_settings(overrides=overrides)
    engine = GoldEngine(settings=day_settings, run_dir=None)
    x = day_settings.bounds.lower
    _f, _g, _flows, raw_results = engine.evaluate_one_with_details(x)
    if not isinstance(raw_results, dict):
        raise TypeError(
            "[build_vienna_constant_thermflex_mechanism_bundle] Gold replay did not return raw_results."
        )
    synthetic_run_dir = RESULT_ROOT / f"_replay_{overrides['run']['tag']}"
    return raw_results, synthetic_run_dir, day_settings


def _write_markdown_summary(
    *,
    output_dir: Path,
    selected_df: pd.DataFrame,
    solar_bins_df: pd.DataFrame,
    cohort_df: pd.DataFrame,
) -> None:
    lines = [
        "# Vienna Constant Thermflex Mechanism Bundle",
        "",
        "This bundle reuses the active `upper_only dur24 evt24` heating-season screen and extracts one small, paper-oriented mechanism subset.",
        "",
        "## Selected day classes",
        "",
    ]
    for row in selected_df.itertuples(index=False):
        lines.extend(
            [
                f"### {row.selection_label}",
                "",
                f"- Date: `{row.date}`",
                f"- Rationale: {row.selection_rationale}",
                f"- Cost change: `{float(row.dispatch_operating_cost_pct_change):.2f} %`",
                f"- CO2 change: `{float(row.co2_emissions_total_pct_change):.2f} %`",
                f"- Boiler energy change: `{float(row.district_gas_boiler_generation_pct_change):.2f} %`",
                f"- Boiler peak change: `{float(row.district_gas_boiler_peak_pct_change):.2f} %`",
                f"- Shifted heat: `{float(row.thermflex_shifted_space_heat_kwh) / 1e3:.1f} MWh`",
                f"- Rebound / shifted: `{float(row.thermflex_rebound_over_shifted_pct):.1f} %`"
                if pd.notna(row.thermflex_rebound_over_shifted_pct)
                else "- Rebound / shifted: `n/a`",
                f"- Solar proxy sum: `{float(row.solargains_proxy_sum_ctx):.0f}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Solar bin summary",
            "",
        ]
    )
    for row in solar_bins_df.itertuples(index=False):
        lines.append(
            "- "
            f"`{row.solar_bin}` | days `{int(row.day_count)}` | "
            f"mean shifted `{float(row.mean_shifted_heat_mwh):.1f} MWh` | "
            f"mean cost `{float(row.mean_cost_change_pct):.2f} %` | "
            f"mean CO2 `{float(row.mean_co2_change_pct):.2f} %` | "
            f"mean rebound/shifted `{float(row.mean_rebound_over_shifted_pct):.1f} %`"
        )

    lines.extend(
        [
            "",
            "## Residential cohort highlights",
            "",
        ]
    )
    for label in SELECTED_DAY_ORDER:
        day_slice = cohort_df.loc[cohort_df["selection_label"] == label].copy()
        if day_slice.empty:
            continue
        day_slice = day_slice.sort_values("cohort_shifted_wh_per_m2", ascending=False)
        top = day_slice.iloc[0]
        modern = day_slice.loc[day_slice["cohort_key"] == "residential_2000_2014"]
        old = day_slice.loc[day_slice["cohort_key"] == "residential_pre1975"]
        lines.append(f"### {label}")
        lines.append("")
        lines.append(
            f"- Highest shifted intensity: `{top['cohort_key']}` -> `{float(top['cohort_shifted_wh_per_m2']):.1f} Wh/m2`"
        )
        if not old.empty and not modern.empty:
            lines.append(
                f"- `pre1975` vs `2000_2014`: `{float(old.iloc[0]['cohort_shifted_wh_per_m2']):.1f}` vs "
                f"`{float(modern.iloc[0]['cohort_shifted_wh_per_m2']):.1f} Wh/m2` shifted; "
                f"`max dT_in {float(old.iloc[0]['cohort_max_delta_t_in_k']):.2f}` vs "
                f"`{float(modern.iloc[0]['cohort_max_delta_t_in_k']):.2f} K`"
            )
        lines.append("")

    (output_dir / "mechanism_bundle_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    out = build_vienna_constant_thermflex_mechanism_bundle()
    print(f"[build_vienna_constant_thermflex_mechanism_bundle] output_dir={out}", flush=True)
