from __future__ import annotations

"""Build paper tables from the latest Vienna thermflex mechanism bundle."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESULT_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
TABLE_DIR = PROJECT_ROOT / "Documentation" / "Papers" / "thermflex_paper" / "tables"

TABLE_10 = TABLE_DIR / "table_10_mechanism_day_classes_upper_only_dur24.md"
TABLE_11 = TABLE_DIR / "table_11_solar_bin_summary_upper_only_dur24.md"
TABLE_12 = TABLE_DIR / "table_12_selected_day_residential_cohort_intensity_upper_only_dur24.md"


def build_mechanism_tables_from_latest_bundle() -> list[Path]:
    bundle_dir = _resolve_latest_bundle_dir()
    selected_df = pd.read_csv(bundle_dir / "selected_days.csv")
    solar_df = pd.read_csv(bundle_dir / "solar_bin_summary.csv")
    cohort_df = pd.read_csv(bundle_dir / "selected_day_cohort_summary.csv")

    _write_table_10(selected_df)
    _write_table_11(solar_df)
    _write_table_12(cohort_df)
    return [TABLE_10, TABLE_11, TABLE_12]


def _resolve_latest_bundle_dir() -> Path:
    matches = [
        path
        for path in RESULT_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("paper_mechanism_bundle_")
    ]
    if not matches:
        raise FileNotFoundError(
            "[build_mechanism_tables_from_latest_bundle] no `paper_mechanism_bundle_*` result dir found."
        )
    matches.sort(key=lambda path: path.name, reverse=True)
    return matches[0]


def _write_table_10(selected_df: pd.DataFrame) -> None:
    required = [
        "selection_label",
        "date",
        "t_outdoor_mean_c",
        "dispatch_operating_cost_pct_change",
        "co2_emissions_total_pct_change",
        "district_gas_boiler_generation_pct_change",
        "district_gas_boiler_peak_pct_change",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_over_shifted_pct",
    ]
    _require_columns(selected_df, required, table_name="table_10")
    label_map = {
        "best_joint_savings": "best joint savings",
        "robust_savings": "robust savings",
        "cold_contrast": "cold contrast",
        "co2_tradeoff": "CO2 trade-off",
        "late_season_near_neutral": "late-season near-neutral",
    }
    reading_map = {
        "best_joint_savings": "Best all-round day with strong boiler and peak relief.",
        "robust_savings": "Savings remain strong without relying on a lower peak hour everywhere.",
        "cold_contrast": "Very cold day with little system value despite active heat demand.",
        "co2_tradeoff": "Thermal activity is visible, but CO2 worsens slightly.",
        "late_season_near_neutral": "Thermal movement remains visible while system KPIs are almost flat.",
    }
    lines = [
        "| Day class | Date | Mean outdoor temperature [degC] | Cost change [%] | CO2 change [%] | Boiler energy change [%] | Boiler peak change [%] | Shifted heat [MWh] | Rebound / shifted [%] | Reading |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in selected_df.itertuples(index=False):
        rebound = (
            f"{float(row.thermflex_rebound_over_shifted_pct):.1f}"
            if pd.notna(row.thermflex_rebound_over_shifted_pct)
            else "n/a"
        )
        lines.append(
            "| "
            f"{label_map.get(str(row.selection_label), str(row.selection_label))} | "
            f"{row.date} | "
            f"{float(row.t_outdoor_mean_c):.1f} | "
            f"{float(row.dispatch_operating_cost_pct_change):.2f} | "
            f"{float(row.co2_emissions_total_pct_change):.2f} | "
            f"{float(row.district_gas_boiler_generation_pct_change):.2f} | "
            f"{float(row.district_gas_boiler_peak_pct_change):.2f} | "
            f"{float(row.thermflex_shifted_space_heat_kwh) / 1e3:.1f} | "
            f"{rebound} | "
            f"{reading_map.get(str(row.selection_label), '')} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- This table is built from the latest full heating-season `upper_only dur24 evt24` screen.",
            "- It is meant to separate robust savings days from cold-contrast and late-season trade-off days, not to claim one universal mechanism.",
        ]
    )
    TABLE_10.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_table_11(solar_df: pd.DataFrame) -> None:
    required = [
        "solar_bin",
        "day_count",
        "mean_shifted_heat_mwh",
        "mean_cost_change_pct",
        "mean_co2_change_pct",
        "mean_rebound_over_shifted_pct",
    ]
    _require_columns(solar_df, required, table_name="table_11")
    lines = [
        "| Solar bin | Days [n] | Mean shifted heat [MWh/day] | Mean cost change [%] | Mean CO2 change [%] | Mean rebound / shifted [%] | Reading |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    reading_map = {
        "low solar": "Low-solar heating days shift the least, but average KPI savings are still visible.",
        "mid solar": "Mid-solar days currently deliver the strongest average cost and CO2 gains.",
        "high solar": "High-solar days shift the most heat, but many late shoulder days dilute the average KPI benefit.",
    }
    for row in solar_df.itertuples(index=False):
        lines.append(
            "| "
            f"{row.solar_bin} | "
            f"{int(row.day_count)} | "
            f"{float(row.mean_shifted_heat_mwh):.1f} | "
            f"{float(row.mean_cost_change_pct):.2f} | "
            f"{float(row.mean_co2_change_pct):.2f} | "
            f"{float(row.mean_rebound_over_shifted_pct):.1f} | "
            f"{reading_map.get(str(row.solar_bin), '')} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- More solar does not automatically mean larger average system benefit.",
            "- In the current full-season screen, solar mainly increases available thermal movement; the strongest average KPI gains sit in the mid-solar bin.",
        ]
    )
    TABLE_11.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_table_12(cohort_df: pd.DataFrame) -> None:
    required = [
        "selection_label",
        "date",
        "cohort_key",
        "cohort_shifted_wh_per_m2",
        "cohort_preheat_wh_per_m2",
        "cohort_cutback_wh_per_m2",
        "cohort_max_delta_t_in_k",
    ]
    _require_columns(cohort_df, required, table_name="table_12")
    label_map = {
        "best_joint_savings": "best joint savings",
        "robust_savings": "robust savings",
        "cold_contrast": "cold contrast",
        "co2_tradeoff": "CO2 trade-off",
        "late_season_near_neutral": "late-season near-neutral",
    }
    cohort_order = {
        "residential_pre1975": 0,
        "residential_1975_1990": 1,
        "residential_1990_2000": 2,
        "residential_2000_2014": 3,
    }
    ordered = cohort_df.copy()
    ordered["selection_order"] = ordered["selection_label"].map(
        {key: idx for idx, key in enumerate(label_map.keys())}
    )
    ordered["cohort_order"] = ordered["cohort_key"].map(cohort_order)
    ordered = ordered.sort_values(["selection_order", "cohort_order"]).reset_index(drop=True)
    lines = [
        "| Day class | Date | Residential cohort | Shifted heat [Wh/m2] | Preheat realized [Wh/m2] | Cutback realized [Wh/m2] | Max Delta T_in [K] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in ordered.itertuples(index=False):
        cohort_label = str(row.cohort_key).replace("residential_", "").replace("_", "-")
        lines.append(
            "| "
            f"{label_map.get(str(row.selection_label), str(row.selection_label))} | "
            f"{row.date} | "
            f"{cohort_label} | "
            f"{float(row.cohort_shifted_wh_per_m2):.1f} | "
            f"{float(row.cohort_preheat_wh_per_m2):.1f} | "
            f"{float(row.cohort_cutback_wh_per_m2):.1f} | "
            f"{float(row.cohort_max_delta_t_in_k):.2f} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- On the selected `dur24` days, older residential cohorts still dominate shifted intensity in `Wh/m2`.",
            "- The newest cohort shows much smaller `Delta T_in` and shifted intensity on the top-savings days, so the current paper story should focus on persistence and use conditions rather than naively claiming higher shifted `kWh` for newer buildings.",
        ]
    )
    TABLE_12.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _require_columns(df: pd.DataFrame, required: list[str], *, table_name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"[{table_name}] missing required columns: {missing}")


if __name__ == "__main__":
    for path in build_mechanism_tables_from_latest_bundle():
        print(path)
