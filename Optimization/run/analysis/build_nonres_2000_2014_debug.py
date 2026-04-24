from __future__ import annotations

"""Debug the apparent zero-flex day for non_residential_2000_2014."""

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from Optimization.run.analysis.dh_thermflex_inputs import (
    load_vienna_dh_thermflex_full_year_context,
)


TARGET_COHORT_KEY = "non_residential_2000_2014"
TARGET_DATE = pd.Timestamp("2023-01-08")


def build_nonres_2000_2014_debug_bundle(output_dir: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    context = load_vienna_dh_thermflex_full_year_context()
    if TARGET_COHORT_KEY not in context.member_hourly_frames:
        raise KeyError(
            f"[nonres_2000_2014_debug] Cohort '{TARGET_COHORT_KEY}' is missing in the yearly context."
        )
    hourly = context.member_hourly_frames[TARGET_COHORT_KEY].copy()
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"])
    hourly = hourly.set_index("timestamp")

    daily = hourly.resample("D").agg(
        {
            "space_heat_kwh": "sum",
            "hotwater_kwh": "sum",
            "dh_space_heat_kwh": "sum",
            "dh_hotwater_kwh": "sum",
            "dh_total_kwh": "sum",
            "electric_load_kwh": "sum",
            "hp_elec_heat_kwh": "sum",
            "hp_elec_cool_kwh": "sum",
            "t_outdoor_c": ["mean", "min", "max"],
            "irradiance_proxy": "sum",
            "solargains_proxy": "sum",
        }
    )
    daily.columns = _flatten_columns(daily.columns)
    daily = daily.rename(
        columns={
            "space_heat_kwh_sum": "space_heat_kwh",
            "hotwater_kwh_sum": "hotwater_kwh",
            "dh_space_heat_kwh_sum": "dh_space_heat_kwh",
            "dh_hotwater_kwh_sum": "dh_hotwater_kwh",
            "dh_total_kwh_sum": "dh_total_kwh",
            "electric_load_kwh_sum": "electric_load_kwh",
            "hp_elec_heat_kwh_sum": "hp_elec_heat_kwh",
            "hp_elec_cool_kwh_sum": "hp_elec_cool_kwh",
            "irradiance_proxy_sum": "irradiance_proxy",
            "solargains_proxy_sum": "solargains_proxy",
            "t_outdoor_c_mean": "t_outdoor_mean_c",
            "t_outdoor_c_min": "t_outdoor_min_c",
            "t_outdoor_c_max": "t_outdoor_max_c",
        }
    )
    daily.index.name = "date"
    daily.to_csv(output_dir / "nonres_2000_2014_daily.csv", index=True)

    suspicious_window = hourly.loc["2023-01-06 00:00:00":"2023-01-09 23:00:00"].copy()
    if suspicious_window.empty:
        raise ValueError("[nonres_2000_2014_debug] Expected non-empty 4-day hourly debug window.")
    suspicious_window.to_csv(output_dir / "nonres_2000_2014_hourly_window.csv", index=True)

    if TARGET_DATE not in daily.index:
        raise KeyError(
            f"[nonres_2000_2014_debug] Target paper date {TARGET_DATE.date()} is missing in the daily table."
        )

    daily_rank = int(
        daily["space_heat_kwh"]
        .rank(method="min", ascending=False)
        .loc[TARGET_DATE]
    )
    peak_day = daily["space_heat_kwh"].idxmax()
    summary = {
        "cohort_key": TARGET_COHORT_KEY,
        "paper_slice_date": str(TARGET_DATE.date()),
        "paper_slice_space_heat_kwh": float(daily.loc[TARGET_DATE, "space_heat_kwh"]),
        "paper_slice_hotwater_kwh": float(daily.loc[TARGET_DATE, "hotwater_kwh"]),
        "paper_slice_dh_space_heat_kwh": float(daily.loc[TARGET_DATE, "dh_space_heat_kwh"]),
        "paper_slice_t_outdoor_mean_c": float(daily.loc[TARGET_DATE, "t_outdoor_mean_c"]),
        "paper_slice_t_outdoor_min_c": float(daily.loc[TARGET_DATE, "t_outdoor_min_c"]),
        "annual_space_heat_kwh": float(daily["space_heat_kwh"].sum()),
        "annual_hotwater_kwh": float(daily["hotwater_kwh"].sum()),
        "annual_dh_space_heat_kwh": float(daily["dh_space_heat_kwh"].sum()),
        "n_nonzero_space_heat_days": int((daily["space_heat_kwh"] > 1e-9).sum()),
        "space_heat_day_rank_descending": daily_rank,
        "peak_space_heat_day": str(peak_day.date()),
        "peak_space_heat_kwh": float(daily.loc[peak_day, "space_heat_kwh"]),
        "paper_day_is_zero_space_heat": bool(abs(float(daily.loc[TARGET_DATE, "space_heat_kwh"])) <= 1e-9),
        "paper_day_is_zero_hotwater": bool(abs(float(daily.loc[TARGET_DATE, "hotwater_kwh"])) <= 1e-9),
        "interpretation": [
            "The cohort is not globally broken: annual space heat is non-zero and many winter days carry substantial load.",
            "The suspicious paper slice day itself is zero for space heat in this cohort.",
            "Hot water is zero for this non-residential cohort over the full year by model design, but that does not explain the zero space-heat day.",
        ],
        "source_override_path": str(context.source_override_path),
    }
    (output_dir / "nonres_2000_2014_debug_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_summary_markdown(output_dir=output_dir, summary=summary)
    _save_debug_plot(output_dir=output_dir, daily=daily, hourly_window=suspicious_window)
    return output_dir


def _flatten_columns(columns: pd.Index) -> list[str]:
    flat: list[str] = []
    for col in columns:
        if not isinstance(col, tuple):
            flat.append(str(col))
            continue
        flat.append("_".join(str(part) for part in col if str(part)))
    return flat


def _write_summary_markdown(*, output_dir: Path, summary: dict[str, object]) -> None:
    lines = [
        "# non_residential_2000_2014 Debug Summary",
        "",
        f"- Paper slice date: `{summary['paper_slice_date']}`",
        f"- Paper slice space heat: `{float(summary['paper_slice_space_heat_kwh']):.1f} kWh`",
        f"- Paper slice hot water: `{float(summary['paper_slice_hotwater_kwh']):.1f} kWh`",
        f"- Annual space heat: `{float(summary['annual_space_heat_kwh']) / 1e6:.3f} GWh`",
        f"- Annual hot water: `{float(summary['annual_hotwater_kwh']) / 1e6:.3f} GWh`",
        f"- Non-zero space-heat days: `{int(summary['n_nonzero_space_heat_days'])}`",
        f"- Peak space-heat day: `{summary['peak_space_heat_day']}` with `{float(summary['peak_space_heat_kwh']) / 1e6:.3f} GWh`",
        "",
        "Interpretation:",
    ]
    for item in summary["interpretation"]:
        lines.append(f"- {item}")
    (output_dir / "nonres_2000_2014_debug_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _save_debug_plot(
    *,
    output_dir: Path,
    daily: pd.DataFrame,
    hourly_window: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=False)

    axes[0].plot(daily.index, daily["space_heat_kwh"] / 1e6, color="#b45309", linewidth=1.4)
    axes[0].scatter([TARGET_DATE], [daily.loc[TARGET_DATE, "space_heat_kwh"] / 1e6], color="#dc2626", s=55, zorder=5)
    axes[0].axvline(TARGET_DATE, color="#dc2626", linestyle="--", linewidth=1.0, alpha=0.8)
    axes[0].set_title("non_residential_2000_2014: daily space heat over 2023")
    axes[0].set_ylabel("Space heat [GWh/day]")
    axes[0].grid(True, alpha=0.25)
    axes[0].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    x = hourly_window.index
    axes[1].plot(x, hourly_window["space_heat_kwh"] / 1e3, label="Space heat", color="#b45309", linewidth=2.0)
    axes[1].plot(x, hourly_window["electric_load_kwh"] / 1e3, label="Electric load", color="#2563eb", linewidth=1.5)
    axes[1].plot(x, hourly_window["hp_elec_heat_kwh"] / 1e3, label="HP heat electricity", color="#059669", linewidth=1.5)
    axes[1].plot(x, hourly_window["hp_elec_cool_kwh"] / 1e3, label="HP cool electricity", color="#7c3aed", linewidth=1.5)
    axes[1].axvspan(
        pd.Timestamp("2023-01-08 00:00:00"),
        pd.Timestamp("2023-01-08 23:00:00"),
        color="#fca5a5",
        alpha=0.25,
        label="paper day",
    )
    ax2 = axes[1].twinx()
    ax2.plot(x, hourly_window["t_outdoor_c"], color="#111827", linestyle="--", linewidth=1.2, label="Outdoor T")
    ax2.set_ylabel("Outdoor temperature [C]")

    axes[1].set_title("Hourly window around the paper day")
    axes[1].set_ylabel("Energy / hour [MWh/h]")
    axes[1].grid(True, alpha=0.25)
    axes[1].xaxis.set_major_locator(mdates.HourLocator(interval=12))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %Hh"))

    lines_left, labels_left = axes[1].get_legend_handles_labels()
    lines_right, labels_right = ax2.get_legend_handles_labels()
    axes[1].legend(lines_left + lines_right, labels_left + labels_right, loc="upper left", ncol=3)

    fig.tight_layout()
    fig.savefig(output_dir / "nonres_2000_2014_debug.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
