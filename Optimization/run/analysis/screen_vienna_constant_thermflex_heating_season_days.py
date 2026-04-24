from __future__ import annotations

"""Systematically screen Vienna heating-season days for the active paper flex case.

This helper intentionally stays close to the current paper question:
- fixed current Vienna system,
- direct gold replay of fixed daily slices,
- explicit REF vs active `upper_only dur24 evt24`,
- ranking by daily cost / CO2 / boiler effects.

There is no hidden optimization layer here. The paper cases already encode fixed
design and dispatch settings through overrides and degenerate bounds. Replaying
the lower design bound therefore reproduces the active case directly and avoids
unnecessary optimizer overhead for hundreds of daily 24 h slices.
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt


def _bootstrap_project_root() -> Path:
    """Resolve the repository root once and fail loudly if the structure changed."""

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
            project_root = parent
            break
    else:
        raise RuntimeError(
            "[screen_vienna_constant_thermflex_heating_season_days] project root not found."
        )
    project_root_str = str(project_root.resolve())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from Settings import get_settings  # noqa: E402
from Optimization.framework.engines.Gold.gold_engine import GoldEngine  # noqa: E402
from Optimization.run.analysis.csv_exports import build_dispatch_kpi_payload  # noqa: E402
from Optimization.run.analysis.select_vienna_dh_thermflex_representative_days import (  # noqa: E402
    _build_daily_features,
)
from Optimization.run.analysis.dh_thermflex_inputs import (  # noqa: E402
    load_vienna_dh_thermflex_full_year_context,
)


OVERRIDE_DIR = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
REF_OVERRIDE = OVERRIDE_DIR / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
FLEX_OVERRIDE = (
    OVERRIDE_DIR
    / "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json"
)
RESULT_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
HEATING_SEASON_MONTHS = {1, 2, 3, 4, 10, 11, 12}
FLEX_CASE_LABEL = "UPPER_24H"


@dataclass(frozen=True)
class ScreenCase:
    """Minimal case descriptor for the daily screen."""

    label: str
    override_path: Path


SCREEN_CASES = (
    ScreenCase(label="REF", override_path=REF_OVERRIDE),
    ScreenCase(label=FLEX_CASE_LABEL, override_path=FLEX_OVERRIDE),
)


def _load_overrides(path: Path) -> dict[str, Any]:
    """Read one override file exactly once and fail on missing inputs."""

    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(
            "[screen_vienna_constant_thermflex_heating_season_days] override file not found: "
            f"{path}"
        )
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _pct_delta(new_value: float, ref_value: float) -> float | None:
    """Return explicit percent deltas and keep zero baselines visible as None."""

    if abs(ref_value) < 1e-12:
        return None
    return float(100.0 * (new_value - ref_value) / ref_value)


def _evaluate_day_slice(*, case: ScreenCase, day_date: str) -> dict[str, Any]:
    """Replay one explicit 24 h day slice through the gold engine.

    This uses the fixed paper override directly. Since the bounds are already
    degenerate for the active paper cases, evaluating the lower bound is the
    exact active design and avoids any hidden optimizer pass.
    """

    overrides = _load_overrides(case.override_path)
    overrides["run"]["profile_start"] = f"{day_date} 00:00:00"
    overrides["run"]["profile_hours"] = 24
    overrides["run"]["tag"] = f"{case.override_path.stem}_{day_date.replace('-', '')}_screen"
    settings = get_settings(overrides=overrides)
    engine = GoldEngine(settings=settings, run_dir=None)
    x = np.asarray(settings.bounds.lower, dtype=float)
    _F, _G, flows_L, raw_results = engine._evaluate_one_core(x)
    payload = build_dispatch_kpi_payload(
        settings=settings,
        flows_L=flows_L,
        raw_results=raw_results,
        point_idx=0,
    )
    payload["case_label"] = case.label
    payload["override_name"] = case.override_path.name
    payload["date"] = day_date
    return payload


def _build_daily_context() -> pd.DataFrame:
    """Build one explicit daily context table from the active REF SSOT override."""

    context = load_vienna_dh_thermflex_full_year_context(base_override_path=REF_OVERRIDE)
    daily = _build_daily_features(context)
    if "is_heating_day" not in daily.columns:
        raise KeyError(
            "[screen_vienna_constant_thermflex_heating_season_days] daily context missing 'is_heating_day'."
        )
    return daily


def _select_screen_days(daily: pd.DataFrame) -> pd.DataFrame:
    """Limit the screen to explicit heating days only.

    This keeps the exercise aligned with the user question: we are not looking
    for savings on pure hot-water summer days, but on thermflex-relevant days.
    """

    heating_days = daily[
        daily["is_heating_day"] & daily.index.month.isin(sorted(HEATING_SEASON_MONTHS))
    ].copy()
    if heating_days.empty:
        raise ValueError(
            "[screen_vienna_constant_thermflex_heating_season_days] no heating days found in daily context."
        )
    heating_days = heating_days.reset_index().rename(columns={"date": "day_timestamp"})
    heating_days["date"] = heating_days["day_timestamp"].dt.strftime("%Y-%m-%d")
    return heating_days


def _join_day_results(*, day_row: pd.Series, ref_payload: dict[str, Any], flex_payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble one flat row with explicit baseline, flex and delta fields."""

    row = {
        "date": str(day_row["date"]),
        "t_outdoor_mean_c": float(day_row["t_outdoor_mean_c"]),
        "t_outdoor_min_c": float(day_row["t_outdoor_min_c"]),
        "dh_space_heat_total_kwh": float(day_row["dh_space_heat_total_kwh"]),
        "dh_total_kwh": float(day_row["dh_total_kwh"]),
        "irradiance_proxy_sum": float(day_row["irradiance_proxy_sum"]),
        "solargains_proxy_sum": float(day_row["solargains_proxy_sum"]),
        "mc_auction_mean_eur_mwh": float(day_row["mc_auction_mean_eur_mwh"]),
        "gas_price_mean_eur_mwh_fuel": float(day_row["gas_price_mean_eur_mwh_fuel"]),
        "co2_price_mean_eur_tco2": float(day_row["co2_price_mean_eur_tco2"]),
        "dispatch_operating_cost_eur_ref": float(ref_payload["dispatch_operating_cost_eur"]),
        "dispatch_operating_cost_eur_flex": float(flex_payload["dispatch_operating_cost_eur"]),
        "co2_emissions_total_t_ref": float(ref_payload["co2_emissions_total_t"]),
        "co2_emissions_total_t_flex": float(flex_payload["co2_emissions_total_t"]),
        "district_gas_boiler_peak_kw_ref": float(ref_payload["district_gas_boiler_peak_kw"]),
        "district_gas_boiler_peak_kw_flex": float(flex_payload["district_gas_boiler_peak_kw"]),
        "district_gas_boiler_generation_kwh_ref": float(ref_payload["district_gas_boiler_generation_kwh"]),
        "district_gas_boiler_generation_kwh_flex": float(
            flex_payload["district_gas_boiler_generation_kwh"]
        ),
        "thermflex_shifted_space_heat_kwh": float(flex_payload["thermflex_shifted_space_heat_kwh"]),
        "thermflex_rebound_kwh": float(flex_payload["thermflex_rebound_kwh"]),
        "dh_total_peak_change_kw": float(flex_payload["dh_total_peak_change_kw"]),
        "thermflex_peak_change_kw": float(flex_payload["thermflex_peak_change_kw"]),
        "flex_case_label": str(flex_payload["case_label"]),
        "flex_override_name": str(flex_payload["override_name"]),
    }
    row["dispatch_operating_cost_eur_delta"] = (
        row["dispatch_operating_cost_eur_flex"] - row["dispatch_operating_cost_eur_ref"]
    )
    row["dispatch_operating_cost_pct_change"] = _pct_delta(
        row["dispatch_operating_cost_eur_flex"],
        row["dispatch_operating_cost_eur_ref"],
    )
    row["co2_emissions_total_t_delta"] = (
        row["co2_emissions_total_t_flex"] - row["co2_emissions_total_t_ref"]
    )
    row["co2_emissions_total_pct_change"] = _pct_delta(
        row["co2_emissions_total_t_flex"],
        row["co2_emissions_total_t_ref"],
    )
    row["district_gas_boiler_peak_kw_delta"] = (
        row["district_gas_boiler_peak_kw_flex"] - row["district_gas_boiler_peak_kw_ref"]
    )
    row["district_gas_boiler_peak_pct_change"] = _pct_delta(
        row["district_gas_boiler_peak_kw_flex"],
        row["district_gas_boiler_peak_kw_ref"],
    )
    row["district_gas_boiler_generation_kwh_delta"] = (
        row["district_gas_boiler_generation_kwh_flex"]
        - row["district_gas_boiler_generation_kwh_ref"]
    )
    row["district_gas_boiler_generation_pct_change"] = _pct_delta(
        row["district_gas_boiler_generation_kwh_flex"],
        row["district_gas_boiler_generation_kwh_ref"],
    )
    if row["thermflex_shifted_space_heat_kwh"] > 0.0:
        row["thermflex_rebound_over_shifted_pct"] = float(
            100.0 * row["thermflex_rebound_kwh"] / row["thermflex_shifted_space_heat_kwh"]
        )
    else:
        row["thermflex_rebound_over_shifted_pct"] = None
    cost_gain = max(0.0, -(row["dispatch_operating_cost_pct_change"] or 0.0))
    co2_gain = max(0.0, -(row["co2_emissions_total_pct_change"] or 0.0))
    row["joint_savings_score"] = float(cost_gain + co2_gain)
    return row


def _rank_days(table: pd.DataFrame) -> dict[str, Any]:
    """Create a compact ranking payload for later paper day selection."""

    if table.empty:
        raise ValueError("[screen_vienna_constant_thermflex_heating_season_days] ranking input table is empty.")
    best_cost = table.sort_values("dispatch_operating_cost_pct_change", ascending=True).head(10)
    best_co2 = table.sort_values("co2_emissions_total_pct_change", ascending=True).head(10)
    best_joint = table.sort_values("joint_savings_score", ascending=False).head(10)
    cold_contrast = table.sort_values(
        ["dh_space_heat_total_kwh", "dispatch_operating_cost_pct_change"],
        ascending=[False, True],
    ).head(10)
    return {
        "best_cost_days": best_cost.to_dict(orient="records"),
        "best_co2_days": best_co2.to_dict(orient="records"),
        "best_joint_days": best_joint.to_dict(orient="records"),
        "cold_contrast_days": cold_contrast.to_dict(orient="records"),
    }


def _write_markdown(*, output_dir: Path, table: pd.DataFrame, ranking: dict[str, Any]) -> None:
    """Write a short human-readable summary next to the raw CSV/JSON outputs."""

    lines = [
        "# Heating-Season Daily Thermflex Screen",
        "",
        "Cases:",
        f"- `REF`: `{REF_OVERRIDE.name}`",
        f"- `{FLEX_CASE_LABEL}`: `{FLEX_OVERRIDE.name}`",
        "",
        f"- Heating days screened: `{len(table)}`",
        "",
        "Top days by joint cost + CO2 savings score:",
        "",
    ]
    for item in ranking["best_joint_days"][:10]:
        lines.append(
            "- "
            f"`{item['date']}` | "
            f"cost `{float(item['dispatch_operating_cost_pct_change']):.2f} %` | "
            f"CO2 `{float(item['co2_emissions_total_pct_change']):.2f} %` | "
            f"boiler peak `{float(item['district_gas_boiler_peak_pct_change']):.2f} %` | "
            f"boiler energy `{float(item['district_gas_boiler_generation_pct_change']):.2f} %`"
        )
    (output_dir / "heating_season_day_screen.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _save_plot(*, output_dir: Path, table: pd.DataFrame) -> None:
    """Save one compact scatter plot for fast visual inspection of good days."""

    fig, ax = plt.subplots(figsize=(9, 7))
    scatter = ax.scatter(
        table["dispatch_operating_cost_pct_change"],
        table["co2_emissions_total_pct_change"],
        c=table["t_outdoor_mean_c"],
        cmap="coolwarm",
        alpha=0.75,
    )
    ax.axvline(0.0, color="#555555", linewidth=1.0, linestyle="--")
    ax.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
    ax.set_xlabel("Cost change [%]")
    ax.set_ylabel("CO2 change [%]")
    ax.set_title(f"Heating-season daily REF vs {FLEX_CASE_LABEL} screen")
    ax.grid(True, alpha=0.25)
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Outdoor mean temperature [C]")
    best_joint = table.sort_values("joint_savings_score", ascending=False).head(5)
    for _, row in best_joint.iterrows():
        ax.annotate(
            str(row["date"]),
            (float(row["dispatch_operating_cost_pct_change"]), float(row["co2_emissions_total_pct_change"])),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(output_dir / "heating_season_day_screen_scatter.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def run_heating_season_day_screen() -> Path:
    """Execute the full daily screen and persist explicit ranking artefacts."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RESULT_ROOT / f"daily_thermflex_screen_dur24_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_csv = output_dir / "heating_season_day_screen_checkpoint.csv"
    checkpoint_json = output_dir / "heating_season_day_screen_checkpoint.json"

    daily = _select_screen_days(_build_daily_context())
    rows: list[dict[str, Any]] = []
    for idx, day_row in daily.iterrows():
        day_date = str(day_row["date"])
        print(
            "[screen_vienna_constant_thermflex_heating_season_days] "
            f"{idx + 1}/{len(daily)} | {day_date}",
            flush=True,
        )
        ref_payload = _evaluate_day_slice(case=SCREEN_CASES[0], day_date=day_date)
        flex_payload = _evaluate_day_slice(case=SCREEN_CASES[1], day_date=day_date)
        rows.append(_join_day_results(day_row=day_row, ref_payload=ref_payload, flex_payload=flex_payload))
        pd.DataFrame(rows).to_csv(checkpoint_csv, index=False)
        checkpoint_json.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    table = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    ranking = _rank_days(table)
    table.to_csv(output_dir / "heating_season_day_screen.csv", index=False)
    (output_dir / "heating_season_day_screen.json").write_text(
        json.dumps(table.to_dict(orient="records"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "heating_season_day_screen_ranking.json").write_text(
        json.dumps(ranking, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(output_dir=output_dir, table=table, ranking=ranking)
    _save_plot(output_dir=output_dir, table=table)
    return output_dir


if __name__ == "__main__":
    out = run_heating_season_day_screen()
    print(f"[screen_vienna_constant_thermflex_heating_season_days] output_dir={out}", flush=True)
